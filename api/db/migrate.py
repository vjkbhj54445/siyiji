"""数据库迁移工具。

自动执行所有 SQL 迁移文件。
"""

from __future__ import annotations
import sys
from pathlib import Path
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "automation-hub" / "api" / "db" / "migrations"
DB_PATH = PROJECT_ROOT / "automation-hub" / "data" / "automation_hub.sqlite3"


def run_migrations():
    """执行所有迁移文件。"""
    # 确保数据目录存在
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        # 创建迁移记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        conn.commit()
        
        # 获取已应用的迁移
        cursor = conn.execute("SELECT filename FROM schema_migrations")
        applied = {row["filename"] for row in cursor.fetchall()}
        
        # 获取所有迁移文件
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        
        if not migration_files:
            logger.warning(f"No migration files found in {MIGRATIONS_DIR}")
            return
        
        # 执行未应用的迁移
        for migration_file in migration_files:
            filename = migration_file.name
            
            if filename in applied:
                logger.info(f"⏭️  Skipping {filename} (already applied)")
                continue
            
            logger.info(f"▶️  Applying {filename}...")
            
            try:
                # 读取并执行 SQL
                sql = migration_file.read_text(encoding="utf-8")
                conn.executescript(sql)
                
                # 记录已应用
                from datetime import datetime, timezone
                conn.execute(
                    "INSERT INTO schema_migrations(filename, applied_at) VALUES(?, ?)",
                    (filename, datetime.now(timezone.utc).isoformat())
                )
                conn.commit()
                
                logger.info(f"✅ Applied {filename}")
                
            except Exception as e:
                logger.error(f"❌ Failed to apply {filename}: {e}")
                conn.rollback()
                raise
        
        logger.info("✨ All migrations completed successfully")
        
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
