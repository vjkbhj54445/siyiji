"""Worker V2：统一工具执行入口。

集成策略检查、审批验证、执行器调度、审计日志等完整流程。
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from api.db import get_db_connection
from api.tools.registry import get_tool
from worker.policy_enforce import is_run_approved
from worker.executors.host import HostExecutor
from worker.executors.docker import DockerExecutor
from api.audit.service import log_event
from jsonschema import validate as js_validate
from jsonschema.exceptions import ValidationError


logger = logging.getLogger(__name__)


def now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


def run_tool_job(run_id: str, tool_id: str, args: dict, user_id: str | None = None) -> None:
    """执行工具任务（RQ Job 入口）。
    
    完整流程：
    1. 检查审批状态
    2. 加载工具配置
    3. 选择执行器
    4. 执行工具
    5. 记录审计日志
    
    Args:
        run_id: 运行 ID
        tool_id: 工具 ID
        args: 工具参数
        user_id: 用户 ID（用于审计）
    """
    logger.info(f"Starting run {run_id} for tool {tool_id}")
    
    # 1. 检查审批状态（通常应在 API 侧通过审批后再入队；这里做兜底）
    if not is_run_approved(run_id):
        logger.warning(f"Run {run_id} not approved, skipping execution")
        with get_db_connection() as conn:
            # 如果审批被拒绝/未批准，保持 pending_approval/denied 由审批表决定
            row = conn.execute(
                """SELECT status FROM approval_requests
                   WHERE resource_type='run' AND resource_id=?
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (run_id,),
            ).fetchone()
            approval_status = row["status"] if row else None
            new_status = "denied" if approval_status == "denied" else "pending_approval"
            conn.execute("UPDATE tool_runs SET status=? WHERE id=?", (new_status, run_id))
            conn.commit()

        log_event(
            event_type="run.blocked",
            action="execute",
            status="fail",
            actor_user_id=user_id,
            resource_type="run",
            resource_id=run_id,
            message="Run blocked: not approved",
            meta={"tool_id": tool_id, "approval_status": approval_status},
        )
        return
    
    # 2. 加载工具配置
    tool = get_tool(tool_id)
    if not tool:
        logger.error(f"Tool {tool_id} not found")
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE tool_runs SET status='failed', finished_at=? WHERE id=?",
                (now_iso(), run_id),
            )
            conn.commit()
        return
    
    # 3. 获取运行信息
    with get_db_connection() as conn:
        run = conn.execute(
            "SELECT * FROM tool_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        
        if not run:
            logger.error(f"Run {run_id} not found")
            return
        
        # 更新状态为运行中
        conn.execute(
            "UPDATE tool_runs SET status='running', started_at=? WHERE id=?",
            (now_iso(), run_id),
        )
        conn.commit()
        
        run = dict(run)
    
    # 4. 准备执行环境
    command = json.loads(tool["command_json"])
    cwd = tool.get("cwd")
    timeout = int(tool.get("timeout_sec") or 120)

    # 4.1 参数强校验（args_schema）
    try:
        schema_raw = tool.get("args_schema_json")
        if schema_raw:
            schema = json.loads(schema_raw)
            js_validate(instance=args or {}, schema=schema)
    except ValidationError as e:
        msg = f"args_schema 校验失败: {e.message}"
        logger.warning(msg)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE tool_runs SET status='failed', finished_at=?, error_msg=? WHERE id=?",
                (now_iso(), msg, run_id),
            )
            conn.commit()
        log_event(
            event_type="run.invalid_args",
            action="execute",
            status="fail",
            actor_user_id=user_id,
            resource_type="run",
            resource_id=run_id,
            message=msg,
            meta={"tool_id": tool_id},
        )
        return
    except Exception as e:
        msg = f"args_schema 解析/校验异常: {str(e)}"
        logger.exception(msg)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE tool_runs SET status='failed', finished_at=?, error_msg=? WHERE id=?",
                (now_iso(), msg, run_id),
            )
            conn.commit()
        return

    # 4.2 allowed_paths 白名单检查（尽量保守：只检查常见路径参数）
    def _extract_paths(a: dict) -> list[str]:
        keys = {"path", "file", "files", "dir", "directory", "cwd", "root", "source", "destination", "target"}
        out: list[str] = []
        for k, v in (a or {}).items():
            if k not in keys:
                continue
            if isinstance(v, str) and v.strip():
                out.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        out.append(item)
        return out

    def _is_allowed(raw: str, allowed_prefixes: list[Path], base: Path) -> bool:
        if not allowed_prefixes:
            return True
        candidate = Path(raw)
        try:
            if not candidate.is_absolute():
                candidate = (base / candidate)
            candidate = candidate.resolve(strict=False)
        except Exception:
            return False

        for pref in allowed_prefixes:
            try:
                p = pref
                if str(p) == ".":
                    p = base
                if not p.is_absolute():
                    p = (base / p)
                p = p.resolve(strict=False)
                if candidate == p or p in candidate.parents:
                    return True
            except Exception:
                continue
        return False

    try:
        allowed_raw = tool.get("allowed_paths_json") or "[]"
        allowed_list = json.loads(allowed_raw)
        if not isinstance(allowed_list, list):
            allowed_list = []
    except Exception:
        allowed_list = []

    base_dir = Path(env.get("WORKSPACE") or os.getcwd())
    allowed_prefixes = [Path(str(x)) for x in allowed_list if isinstance(x, str) and x.strip()]
    for pv in _extract_paths(args or {}):
        if not _is_allowed(pv, allowed_prefixes, base_dir):
            msg = f"路径不在 allowed_paths 白名单内: {pv}"
            logger.warning(msg)
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE tool_runs SET status='failed', finished_at=?, error_msg=? WHERE id=?",
                    (now_iso(), msg, run_id),
                )
                conn.commit()
            log_event(
                event_type="run.path_blocked",
                action="execute",
                status="fail",
                actor_user_id=user_id,
                resource_type="run",
                resource_id=run_id,
                message=msg,
                meta={"tool_id": tool_id, "allowed_paths": allowed_list},
            )
            return
    
    # 环境变量
    env = os.environ.copy()
    env["WORKSPACE"] = env.get("WORKSPACE", "/workspace")
    env["DATA_DIR"] = env.get("DATA_DIR", "/data")
    env["RUN_ID"] = run_id
    env["TOOL_ID"] = tool_id
    
    # 为工具参数创建环境变量
    for key, value in args.items():
        env[f"ARG_{key.upper()}"] = str(value)
    
    # 5. 选择执行器
    executor_name = tool.get("executor", "docker")
    if executor_name == "host":
        executor = HostExecutor()
    else:
        # 默认使用 Docker
        executor = DockerExecutor()
    
    logger.info(f"Executing with {executor_name} executor")
    
    # 6. 执行工具
    try:
        exit_code = executor.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stdout_path=run["stdout_path"],
            stderr_path=run["stderr_path"]
        )
        
        status = "succeeded" if exit_code == 0 else "failed"
        logger.info(f"Run {run_id} finished with status={status}, exit_code={exit_code}")
        
        # 更新运行状态
        with get_db_connection() as conn:
            conn.execute(
                """UPDATE tool_runs
                   SET status=?, finished_at=?, exit_code=?
                   WHERE id=?""",
                (status, now_iso(), exit_code, run_id),
            )
            conn.commit()
        
        # 记录审计
        log_event(
            event_type="run.executed",
            action="execute",
            status="success" if exit_code == 0 else "fail",
            actor_user_id=user_id,
            resource_type="run",
            resource_id=run_id,
            message=f"Tool executed with exit code {exit_code}",
            meta={
                "tool_id": tool_id,
                "exit_code": exit_code,
                "duration_sec": None  # TODO: 计算执行时长
            }
        )
        
    except Exception as e:
        logger.exception(f"Run {run_id} failed with exception")
        
        # 更新状态为失败
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE tool_runs SET status='failed', finished_at=? WHERE id=?",
                (now_iso(), run_id),
            )
            conn.commit()
        
        # 记录审计
        log_event(
            event_type="run.failed",
            action="execute",
            status="fail",
            actor_user_id=user_id,
            resource_type="run",
            resource_id=run_id,
            message=f"Tool execution failed: {str(e)}",
            meta={"tool_id": tool_id, "error": str(e)}
        )
