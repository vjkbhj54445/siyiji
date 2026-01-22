"""模块说明：元信息接口。"""

from __future__ import annotations

from fastapi import APIRouter
from datetime import datetime
from api.models import HealthCheck

router = APIRouter()


@router.get("/version")
def version():
    return {"name": "automation-hub", "version": "0.1.0"}

@router.get("/meta/info")
async def get_meta_info():
    """获取系统元信息"""
    return {
        "project": "Automation Hub",
        "version": "1.0.0",
        "description": "一个面向学习者的入门级 DevOps 实践项目",
        "built_with": ["FastAPI", "Redis", "RQ", "Docker", "SQLite"],
        "timestamp": datetime.now()
    }
