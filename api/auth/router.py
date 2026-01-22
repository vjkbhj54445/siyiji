"""认证 API 路由。

提供设备注册、Token 创建/管理、用户信息查询、系统初始化等接口。
"""

from __future__ import annotations
import secrets, uuid, json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.db import get_db_connection
from api.auth.deps import hash_token, get_current_token

router = APIRouter(prefix="/auth", tags=["auth"])


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class BootstrapRequest(BaseModel):
    """初始化请求（仅首次使用）。"""
    admin_name: str = Field(..., description="管理员名称")
    device_name: str = Field(..., description="初始设备名称")
    device_platform: str = Field(..., description="设备平台")


class DeviceCreate(BaseModel):
    name: str = Field(..., description="设备名称")
    platform: str = Field(..., description="平台类型：windows/mac/linux/android/ios")


class TokenCreate(BaseModel):
    device_id: str | None = Field(None, description="关联的设备 ID")
    scopes: list[str] = Field(default_factory=list, description="权限范围列表")
    expires_at: str | None = Field(None, description="过期时间（ISO 格式）")


@router.post("/bootstrap")
def bootstrap(payload: BootstrapRequest):
    """初始化系统：创建管理员用户和初始 token。
    
    安全提示：此接口仅应在首次部署时调用一次。
    生产环境建议通过环境变量或配置文件设置初始凭证。
    """
    with get_db_connection() as conn:
        # 检查是否已有用户
        existing = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="System already initialized"
            )
        
        # 创建管理员用户
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users(id, name, created_at) VALUES(?, ?, ?)",
            (user_id, payload.admin_name, now_iso())
        )
        
        # 创建初始设备
        device_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO devices(id, user_id, name, platform, created_at) VALUES(?, ?, ?, ?, ?)",
            (device_id, user_id, payload.device_name, payload.device_platform, now_iso())
        )
        
        # 创建管理员 token（所有权限）
        raw = secrets.token_urlsafe(32)
        token_id = str(uuid.uuid4())
        admin_scopes = [
            "tool:read", "tool:write", "tool:execute",
            "approval:read", "approval:decide",
            "audit:read", "user:admin"
        ]
        
        conn.execute(
            """INSERT INTO api_tokens(id, user_id, device_id, token_hash, scopes, created_at)
               VALUES(?, ?, ?, ?, ?, ?)""",
            (token_id, user_id, device_id, hash_token(raw),
             json.dumps(admin_scopes, ensure_ascii=False), now_iso())
        )
        conn.commit()
        
        return {
            "message": "System initialized successfully",
            "user_id": user_id,
            "token": raw,  # 仅此处返回明文
            "scopes": admin_scopes
        }


@router.post("/devices")
def create_device(payload: DeviceCreate, token=Depends(get_current_token)):
    device_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO devices(id,user_id,name,platform,created_at) VALUES(?,?,?,?,?)",
                     (device_id, token["user_id"], payload.name, payload.platform, now_iso()))
        conn.commit()
    return {"id": device_id}


@router.post("/tokens")
def create_token(payload: TokenCreate, token=Depends(get_current_token)):
    raw = secrets.token_urlsafe(32)
    token_id = str(uuid.uuid4())
    th = hash_token(raw)
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO api_tokens(id,user_id,device_id,token_hash,scopes,expires_at,created_at)
                         VALUES(?,?,?,?,?,?,?)""",
            (token_id, token["user_id"], payload.device_id, th,
             json.dumps(payload.scopes, ensure_ascii=False), payload.expires_at, now_iso()))
        conn.commit()
    return {"token_id": token_id, "token": raw}


@router.get("/me")
def me(token=Depends(get_current_token)):
    return {"user_id": token["user_id"], "device_id": token.get("device_id"), "scopes": token.get("scopes")}


@router.get("/tokens")
def list_tokens(token=Depends(get_current_token)):
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id,device_id,scopes,expires_at,created_at,revoked_at FROM api_tokens WHERE user_id=?",
            (token["user_id"],)).fetchall()
        return {"tokens": [dict(r) for r in rows]}


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: str, token=Depends(get_current_token)):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM api_tokens WHERE id=? AND user_id=?", (token_id, token["user_id"]))
        if not row.fetchone():
            raise HTTPException(status_code=404, detail="not found")
        conn.execute("UPDATE api_tokens SET revoked_at=? WHERE id=?", (now_iso(), token_id))
        conn.commit()
    return {"revoked": True}
