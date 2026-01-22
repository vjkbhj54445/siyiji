"""模块说明：应用配置定义。"""

from pathlib import Path
from pydantic import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置类"""

    # 项目配置
    APP_NAME: str = "Automation Hub"
    VERSION: str = "0.1.0"

    # 环境标识
    ENVIRONMENT: str = "development"

    # 根目录
    DATA_DIR: Path = BASE_DIR / "data"
    WORKSPACE_DIR: Path = BASE_DIR / "workspace"
    SCRIPTS_DIR: Path = BASE_DIR / "scripts"

    # 数据库配置
    DATABASE_PATH: Path = DATA_DIR / "automation_hub.sqlite3"

    # 运行目录
    RUNS_DIR: Path = DATA_DIR / "runs"

    # 日志目录
    LOGS_DIR: Path = DATA_DIR / "logs"

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    QUEUE_NAME: str = "default"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# 创建全局配置实例
settings = Settings()