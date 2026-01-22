"""模块说明：审批接口路由。"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from api.auth.deps import get_current_token
from api.db import get_db_connection
from datetime import datetime, timezone
import json

import redis
from rq import Queue

from api.config import settings
from worker.jobs_v2 import run_tool_job

router = APIRouter(prefix="/approvals", tags=["approvals"])


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _queue() -> Queue:
    redis_conn = redis.from_url(settings.REDIS_URL)
    name = (settings.QUEUE_NAME.split(",", 1)[0] or "default").strip()
    return Queue(name, connection=redis_conn)


@router.get("")
def list_approvals(status: str = "pending", token=Depends(get_current_token)):
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM approval_requests WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        return {"approvals": [dict(r) for r in rows]}


@router.get("/{approval_id}")
def get_approval(approval_id: str, token=Depends(get_current_token)):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(404, "not found")
        return dict(row)


@router.post("/{approval_id}/approve")
def approve(approval_id: str, note: str = "", token=Depends(get_current_token)):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(404, "not found")
        if row["status"] != "pending":
            raise HTTPException(409, "not pending")
        conn.execute("""UPDATE approval_requests
                         SET status='approved', decided_at=?, decided_by_user_id=?, decision_note=?
                         WHERE id=?""",
                     (now_iso(), token["user_id"], note, approval_id))
        conn.commit()

        # 如果是工具运行审批：批准后入队执行
        if row["resource_type"] == "run":
            run_id = row["resource_id"]
            payload = {}
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:
                payload = {}

            tool_id = payload.get("tool_id")
            args = payload.get("args") or {}
            if tool_id:
                # 将 tool_runs 状态从 pending_approval 推进为 queued
                conn.execute(
                    "UPDATE tool_runs SET status='queued' WHERE id=?",
                    (run_id,),
                )
                conn.commit()
                _queue().enqueue(
                    run_tool_job,
                    run_id=run_id,
                    tool_id=tool_id,
                    args=args,
                    user_id=row.get("created_by_user_id"),
                    job_timeout=180,
                )
    return {"approved": True}


@router.post("/{approval_id}/deny")
def deny(approval_id: str, note: str = "", token=Depends(get_current_token)):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(404, "not found")
        if row["status"] != "pending":
            raise HTTPException(409, "not pending")
        conn.execute("""UPDATE approval_requests
                         SET status='denied', decided_at=?, decided_by_user_id=?, decision_note=?
                         WHERE id=?""",
                     (now_iso(), token["user_id"], note, approval_id))

        # 工具运行：拒绝后标记 tool_runs 为 denied
        if row["resource_type"] == "run":
            run_id = row["resource_id"]
            conn.execute(
                "UPDATE tool_runs SET status='denied', finished_at=?, error_msg=? WHERE id=?",
                (now_iso(), note or "denied", run_id),
            )
        conn.commit()
    return {"denied": True}
