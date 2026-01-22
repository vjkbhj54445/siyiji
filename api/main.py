"""模块说明：API 应用入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from api.routes import health, meta, scripts, tasks, runs, metrics, tool_runs
from api.config import settings
from api import db

# 新增模块路由
from api.auth import router as auth_router
from api.tools import router as tools_router
from api.approvals import router as approvals_router
from api.routes.agent import router as agent_router

logger = logging.getLogger("automation_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logging.basicConfig(level=logging.INFO)
    settings.ensure_dirs()
    logger.info("Initializing database...")
    db.init_db()
    yield


app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)

# 注册路由
app.include_router(health.router)
app.include_router(meta.router, prefix="/meta", tags=["meta"])
app.include_router(scripts.router, prefix="/scripts", tags=["scripts"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(tool_runs.router)

# auth/tools/approvals/agent
app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(approvals_router)
app.include_router(agent_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)