import os
from pathlib import Path
from typing import Optional


class Settings:
    """应用配置类"""
    
    # 项目配置
    APP_NAME: str = "Automation Hub"
    VERSION: str = "0.1.0"
    
    # 数据库配置
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/automation_hub.sqlite3")
    
    # 运行目录
    RUNS_DIR: str = os.getenv("RUNS_DIR", "./data/runs")
    
    # 脚本目录
    SCRIPTS_DIR: str = os.getenv("SCRIPTS_DIR", "./scripts")
    
    # 日志目录
    LOGS_DIR: str = os.getenv("LOGS_DIR", "./data/logs")
    
    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    QUEUE_NAME: str = os.getenv("QUEUE_NAME", "default")
    
    # 环境标识
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


# 创建全局配置实例
settings = Settings()

# 其他常量定义
BASE_DIR = Path(__file__).resolve().parent.parent

# 确保必要目录存在
os.makedirs(settings.RUNS_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs("./data", exist_ok=True)