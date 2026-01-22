"""模块说明：审批服务逻辑。"""

from __future__ import annotations
import uuid, json
from datetime import datetime, timezone
from api.db import get_db_connection


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_approval(user_id: str, device_id: str | None, resource_type: str, resource_id: str,
                    action: str, risk_level: str, reason: str, payload: dict) -> str:
    rid = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO approval_requests
                         (id,created_by_user_id,created_by_device_id,resource_type,resource_id,action,risk_level,
                          request_reason,payload_json,status,created_at)
                         VALUES(?,?,?,?,?,?,?,?,?,'pending',?)""",
            (rid, user_id, device_id, resource_type, resource_id, action, risk_level,
             reason, json.dumps(payload, ensure_ascii=False), now_iso()))
        conn.commit()
    return rid
