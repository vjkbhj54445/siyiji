"""模块说明：运行管理接口。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query

import redis
from rq import Queue

from api.config import settings
from api.db import get_run_by_id, create_run as db_create_run, update_run_status, get_runs
from api.models import RunCreate, RunResponse

from worker.jobs import execute_script_job, load_scripts_manifest

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


def validate_script_exists(script_name: str) -> dict:
    manifest = load_scripts_manifest()
    script = next((s for s in manifest.get("scripts", []) if s.get("id") == script_name or s.get("name") == script_name), None)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


# Redis queue
redis_conn = redis.from_url(settings.REDIS_URL)
queue = Queue(connection=redis_conn)


@router.post("/", response_model=RunResponse)
def create_run_endpoint(payload: RunCreate):
    validate_script_exists(payload.script_name)

    run_id = str(uuid.uuid4())

    success = db_create_run(run_id, payload.script_name, json.dumps(payload.parameters or {}))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create run record")

    queue.enqueue(
        execute_script_job,
        run_id=run_id,
        script_name=payload.script_name,
        parameters=payload.parameters or {},
        job_timeout=300,
    )

    return RunResponse(
        run_id=run_id,
        script_name=payload.script_name,
        parameters=json.dumps(payload.parameters or {}),
        status="queued",
        created_at=datetime.now(),
    )


@router.get("/", response_model=List[RunResponse])
def list_runs(limit: int = 50):
    rows = get_runs()
    limited = rows[:limit]
    res: List[RunResponse] = []
    for r in limited:
        res.append(RunResponse(
            run_id=r.get('run_id'),
            script_name=r.get('script_name'),
            parameters=r.get('parameters'),
            status=r.get('status'),
            created_at=r.get('created_at'),
            started_at=r.get('started_at'),
            completed_at=r.get('completed_at'),
            log_file_path=r.get('log_file_path'),
            result=r.get('result'),
            error_msg=r.get('error_msg'),
        ))
    return res


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str):
    run = get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        run_id=run.get('run_id'),
        script_name=run.get('script_name'),
        parameters=run.get('parameters'),
        status=run.get('status'),
        created_at=run.get('created_at'),
        started_at=run.get('started_at'),
        completed_at=run.get('completed_at'),
        log_file_path=run.get('log_file_path'),
        result=run.get('result'),
        error_msg=run.get('error_msg'),
    )
