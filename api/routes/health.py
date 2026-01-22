"""模块说明：健康检查接口。"""

from datetime import datetime
from fastapi import APIRouter
from api.models import HealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    return HealthCheck(status="healthy", timestamp=datetime.now())
