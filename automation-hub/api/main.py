from fastapi import FastAPI
from api.routes import health, meta, scripts, tasks, runs
from api.config import settings
from api import db

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

# 注册路由
app.include_router(health.router)
app.include_router(meta.router, prefix="/meta", tags=["meta"])
app.include_router(scripts.router, prefix="/scripts", tags=["scripts"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(runs.router, prefix="/runs", tags=["runs"])

@app.on_event("startup")
def startup_event():
    """应用启动时初始化数据库"""
    print("Initializing database...")
    db.init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)