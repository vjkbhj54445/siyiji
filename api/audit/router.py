"""审计 API 路由。

提供审计日志查询接口。
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, Query

from api.auth.deps import require_scope
from api.audit.service import query_events


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def get_audit_events(
    event_type: str | None = Query(None, description="事件类型筛选"),
    resource_type: str | None = Query(None, description="资源类型筛选"),
    actor_user_id: str | None = Query(None, description="操作者筛选"),
    since: str | None = Query(None, description="开始时间（ISO 格式）"),
    until: str | None = Query(None, description="结束时间（ISO 格式）"),
    limit: int = Query(100, description="返回数量限制", le=1000),
    token=Depends(require_scope("audit:read"))
):
    """查询审计事件。
    
    支持多维度筛选：事件类型、资源类型、操作者、时间范围等。
    """
    events = query_events(
        event_type=event_type,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        since=since,
        until=until,
        limit=limit
    )
    
    return {
        "events": events,
        "count": len(events)
    }
