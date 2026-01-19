from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.config import settings
from api.db import get_run_by_id, create_run as db_create_run, update_run_status, get_runs, get_script_by_name

# 导入 Redis 和 RQ 相关模块
import redis
from rq import Queue

from api.models import RunCreate, RunResponse

# 连接到 Redis
redis_conn = redis.from_url(settings.REDIS_URL)
queue = Queue(connection=redis_conn)

# 导入任务执行函数
from worker.jobs import execute_script_job

router = APIRouter()


def tail_text(path: str | None, max_chars: int = 2000) -> str | None:
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


def get_script(script_name: str) -> dict:
    # 加载脚本清单
    from worker.jobs import load_scripts_manifest
    manifest = load_scripts_manifest()
    
    # 在清单中查找脚本，支持按 id 匹配
    script = next((s for s in manifest.get("scripts", []) if s["id"] == script_name), None)
    if not script:
        raise HTTPException(status_code=404, detail="script not found")
    return script


@router.post("/runs", response_model=RunResponse)
def create_run_endpoint(background_tasks: BackgroundTasks, payload: RunCreate):
    # 验证脚本是否存在
    get_script(payload.script_name)
    
    run_id = str(uuid.uuid4())
    
    # 创建运行记录
    success = db_create_run(run_id, payload.script_name, json.dumps(payload.parameters))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create run record")
    
    # 将任务添加到队列中执行
    queue.enqueue(
        execute_script_job,
        run_id=run_id,
        script_name=payload.script_name,
        parameters=payload.parameters or {},
        job_timeout='5m'  # 设置超时时间为5分钟
    )
    
    return RunResponse(
        run_id=run_id,
        script_name=payload.script_name,
        parameters=json.dumps(payload.parameters),  # 将字典转换为JSON字符串以匹配模型定义
        status="queued",
        created_at=datetime.now()
    )


@router.get("/runs", response_model=list[RunResponse])
def list_runs(limit: int = 50):
    runs = get_runs()
    # 限制返回数量
    limited_runs = runs[:limit]
    
    result = []
    for run in limited_runs:
        result.append(RunResponse(
            run_id=run['run_id'],
            script_name=run['script_name'],
            parameters=run['parameters'],  # 已经是JSON字符串格式
            status=run['status'],
            created_at=run['created_at'],
            started_at=run.get('started_at'),
            completed_at=run.get('completed_at')
        ))
    
    return result


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str):
    run = get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunResponse(
        run_id=run['run_id'],
        script_name=run['script_name'],
        parameters=run['parameters'],  # 已经是JSON字符串格式
        status=run['status'],
        created_at=run['created_at'],
        started_at=run.get('started_at'),
        completed_at=run.get('completed_at'),
        log_file_path=run.get('log_file_path'),
        result=run.get('result'),
        error_msg=run.get('error_msg')
    )

from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
import sqlite3

router = APIRouter()

class RunResponse(BaseModel):
    id: int
    script_name: str
    parameters: str
    status: str
    start_time: str
    end_time: str
    triggered_by: str
    result_status: Optional[str]
    failure_type: Optional[str]

class AuditQueryParams(BaseModel):
    script_name: Optional[str] = None
    status: Optional[str] = None
    triggered_by: Optional[str] = None
    result_status: Optional[str] = None
    failure_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@router.get("/runs", response_model=List[RunResponse])
def get_runs(
    script_name: str = Query(None),
    status: str = Query(None),
    triggered_by: str = Query(None),
    result_status: str = Query(None),
    failure_type: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    conn = sqlite3.connect('/data/automation_hub.sqlite3')
    cursor = conn.cursor()
    
    query = "SELECT * FROM runs WHERE 1=1"
    params = []
    
    if script_name:
        query += " AND script_name = ?"
        params.append(script_name)
    if status:
        query += " AND status = ?"
        params.append(status)
    if triggered_by:
        query += " AND triggered_by = ?"
        params.append(triggered_by)
    if result_status:
        query += " AND result_status = ?"
        params.append(result_status)
    if failure_type:
        query += " AND failure_type = ?"
        params.append(failure_type)
    if start_date:
        query += " AND start_time >= ?"
        params.append(start_date)
    if end_date:
        query += " AND start_time <= ?"
        params.append(end_date)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        RunResponse(
            id=row[0], script_name=row[1], parameters=row[2], status=row[3],
            start_time=row[4], end_time=row[5], triggered_by=row[6],
            result_status=row[7], failure_type=row[8]
        ) for row in rows
    ]
