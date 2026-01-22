"""模块说明：认证依赖与校验。"""

from __future__ import annotations
import hashlib
from fastapi import Header, HTTPException
from api.db import get_db_connection


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_token(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    raw = authorization.split(" ", 1)[1].strip()
    th = hash_token(raw)

    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM api_tokens WHERE token_hash=? AND revoked_at IS NULL", (th,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="invalid token")
        return dict(row)
