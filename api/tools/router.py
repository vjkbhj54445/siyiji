"""模块说明：工具注册路由。"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from api.auth.deps import get_current_token
from api.tools.models import ToolUpsert
from api.tools.registry import upsert_tool, get_tool, list_tools

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def _list(token=Depends(get_current_token)):
    return {"tools": list_tools()}


@router.get("/{tool_id}")
def _get(tool_id: str, token=Depends(get_current_token)):
    t = get_tool(tool_id)
    if not t:
        raise HTTPException(status_code=404, detail="not found")
    return t


@router.post("")
def _upsert(payload: ToolUpsert, token=Depends(get_current_token)):
    upsert_tool(payload.model_dump())
    return {"ok": True, "tool_id": payload.id}
