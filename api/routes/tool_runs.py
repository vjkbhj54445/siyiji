"""模块说明：工具运行（tool_runs）接口。

提供基于 tools 表的异步执行能力：
- 创建工具运行（必要时走审批）
- 查询运行状态与输出
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from rq import Queue
from jsonschema import validate as js_validate
from jsonschema.exceptions import ValidationError

from api.auth.deps import get_current_token
from api.config import settings
from api.db import (
    create_tool_run,
    get_tool_run_by_id,
    list_tool_runs,
    update_tool_run_status,
)
from api.tools.registry import get_tool
from api.approvals.service import create_approval

from worker.jobs_v2 import run_tool_job

router = APIRouter(prefix="/tool-runs", tags=["tool-runs"])


def _queue() -> Queue:
    redis_conn = redis.from_url(settings.REDIS_URL)
    name = (settings.QUEUE_NAME.split(",", 1)[0] or "default").strip()
    return Queue(name, connection=redis_conn)


def tail_text(path: str | None, max_chars: int = 4000) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception:
        data = p.read_bytes()
        return data[-max_chars:].decode("utf-8", errors="replace")


def _requires_approval(risk_level: str) -> bool:
    return risk_level in {"write", "exec_high"}


_PATH_ARG_KEYS = {
    "path",
    "file",
    "files",
    "dir",
    "directory",
    "cwd",
    "root",
    "source",
    "destination",
    "target",
}


def _extract_path_values(args: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for k, v in (args or {}).items():
        if k not in _PATH_ARG_KEYS:
            continue
        if isinstance(v, str) and v.strip():
            values.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.strip():
                    values.append(item)
    return values


def _normalize_allowed_prefixes(allowed: List[str]) -> List[Path]:
    # API 侧无法准确知道 worker 的工作目录，这里以“相对路径白名单”为主，尽量阻止目录穿越。
    prefixes: List[Path] = []
    for p in allowed or []:
        p = (p or "").strip()
        if not p:
            continue
        prefixes.append(Path(p))
    return prefixes


def _path_is_allowed(raw: str, allowed_prefixes: List[Path]) -> bool:
    # 若未配置 allowed_paths，则默认放行（兼容旧工具）；推荐工具明确配置 allowed_paths。
    if not allowed_prefixes:
        return True

    candidate = Path(raw)
    # 绝对路径：必须落在某个绝对 allowed 前缀下
    if candidate.is_absolute():
        for pref in allowed_prefixes:
            if pref.is_absolute() and (candidate == pref or pref in candidate.parents):
                return True
        return False

    # 相对路径：禁止目录穿越，并要求以某个 allowed 前缀开头
    parts = candidate.parts
    if any(part == ".." for part in parts):
        return False

    for pref in allowed_prefixes:
        if pref == Path("."):
            return True
        try:
            # 例如 pref='tests'，candidate='tests/a.py'
            rel = candidate
            if rel == pref or pref in rel.parents:
                return True
        except Exception:
            continue
    return False


def _validate_args_and_paths(tool: dict, args: Dict[str, Any]) -> None:
    schema_raw = tool.get("args_schema_json")
    if schema_raw:
        try:
            schema = json.loads(schema_raw)
            js_validate(instance=args or {}, schema=schema)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"args_schema 校验失败: {e.message}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"args_schema 解析/校验异常: {str(e)}")

    allowed_raw = tool.get("allowed_paths_json") or "[]"
    try:
        allowed_list = json.loads(allowed_raw)
        if not isinstance(allowed_list, list):
            allowed_list = []
    except Exception:
        allowed_list = []

    allowed_prefixes = _normalize_allowed_prefixes([str(x) for x in allowed_list if isinstance(x, (str, int, float))])
    for pv in _extract_path_values(args or {}):
        if not _path_is_allowed(pv, allowed_prefixes):
            raise HTTPException(status_code=403, detail=f"路径不在 allowed_paths 白名单内: {pv}")


class ToolRunCreate(BaseModel):
    tool_id: str = Field(min_length=1)
    args: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", description="审批原因（可选）")


class ToolRunResponse(BaseModel):
    run_id: str
    tool_id: str
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    approval_id: Optional[str] = None
    stdout_tail: Optional[str] = None
    stderr_tail: Optional[str] = None
    error_msg: Optional[str] = None


@router.post("", response_model=ToolRunResponse)
def create_tool_run_endpoint(payload: ToolRunCreate, token=Depends(get_current_token)):
    tool = get_tool(payload.tool_id)
    if not tool or not int(tool.get("is_enabled", 1)):
        raise HTTPException(status_code=404, detail="tool not found")

    _validate_args_and_paths(tool, payload.args)

    run_id = str(uuid.uuid4())

    run_dir = Path(settings.RUNS_DIR) / "tool_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = str(run_dir / "stdout.txt")
    stderr_path = str(run_dir / "stderr.txt")

    risk_level = tool.get("risk_level", "exec_low")
    user_id = token.get("user_id")

    approval_id: str | None = None
    status = "queued"

    if _requires_approval(risk_level):
        status = "pending_approval"
        approval_id = create_approval(
            user_id=user_id,
            device_id=token.get("device_id"),
            resource_type="run",
            resource_id=run_id,
            action="execute",
            risk_level=risk_level,
            reason=payload.reason or f"execute tool {payload.tool_id}",
            payload={"tool_id": payload.tool_id, "args": payload.args, "run_id": run_id},
        )

    ok = create_tool_run(
        run_id=run_id,
        tool_id=payload.tool_id,
        args=payload.args,
        status=status,
        created_by_user_id=user_id,
        approval_request_id=approval_id,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="failed to create tool run")

    if status == "queued":
        _queue().enqueue(
            run_tool_job,
            run_id=run_id,
            tool_id=payload.tool_id,
            args=payload.args,
            user_id=user_id,
            job_timeout=int(tool.get("timeout_sec") or 120) + 30,
        )

    row = get_tool_run_by_id(run_id) or {}
    return ToolRunResponse(
        run_id=run_id,
        tool_id=payload.tool_id,
        status=row.get("status", status),
        created_at=row.get("created_at"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        exit_code=row.get("exit_code"),
        approval_id=approval_id,
        stdout_tail=tail_text(row.get("stdout_path")),
        stderr_tail=tail_text(row.get("stderr_path")),
        error_msg=row.get("error_msg"),
    )


@router.get("", response_model=List[ToolRunResponse])
def list_tool_runs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    token=Depends(get_current_token),
):
    rows = list_tool_runs(limit=limit)
    res: List[ToolRunResponse] = []
    for r in rows:
        res.append(
            ToolRunResponse(
                run_id=r.get("id"),
                tool_id=r.get("tool_id"),
                status=r.get("status"),
                created_at=r.get("created_at"),
                started_at=r.get("started_at"),
                finished_at=r.get("finished_at"),
                exit_code=r.get("exit_code"),
                approval_id=r.get("approval_request_id"),
                stdout_tail=tail_text(r.get("stdout_path")),
                stderr_tail=tail_text(r.get("stderr_path")),
                error_msg=r.get("error_msg"),
            )
        )
    return res


@router.get("/{run_id}", response_model=ToolRunResponse)
def get_tool_run_endpoint(run_id: str, token=Depends(get_current_token)):
    r = get_tool_run_by_id(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")

    return ToolRunResponse(
        run_id=r.get("id"),
        tool_id=r.get("tool_id"),
        status=r.get("status"),
        created_at=r.get("created_at"),
        started_at=r.get("started_at"),
        finished_at=r.get("finished_at"),
        exit_code=r.get("exit_code"),
        approval_id=r.get("approval_request_id"),
        stdout_tail=tail_text(r.get("stdout_path")),
        stderr_tail=tail_text(r.get("stderr_path")),
        error_msg=r.get("error_msg"),
    )
