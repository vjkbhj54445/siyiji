"""
定时任务调度系统

基于APScheduler实现定时执行工具
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """定时任务配置"""
    id: str
    name: str
    tool_id: str
    args_json: str
    trigger_type: str  # cron / interval / date
    trigger_config: str  # JSON格式的触发器配置
    enabled: bool = True
    created_by: str = "system"
    created_at: str = ""
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    run_count: int = 0


class SchedulerService:
    """定时任务调度服务"""
    
    def __init__(self, db_path: str):
        """
        初始化调度器
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.scheduler = BackgroundScheduler()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                args_json TEXT DEFAULT '{}',
                trigger_type TEXT NOT NULL,
                trigger_config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TEXT NOT NULL,
                last_run_at TEXT,
                next_run_at TEXT,
                run_count INTEGER DEFAULT 0,
                FOREIGN KEY (tool_id) REFERENCES tools(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def start(self):
        """启动调度器"""
        # 从数据库加载所有启用的任务
        self._load_jobs()
        self.scheduler.start()
        logger.info("调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
        logger.info("调度器已关闭")
    
    def _load_jobs(self):
        """从数据库加载任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, tool_id, args_json, trigger_type, trigger_config
            FROM scheduled_jobs
            WHERE enabled = 1
        """)
        
        for row in cursor.fetchall():
            job_id, name, tool_id, args_json, trigger_type, trigger_config = row
            
            try:
                self._add_scheduler_job(
                    job_id=job_id,
                    tool_id=tool_id,
                    args_json=args_json,
                    trigger_type=trigger_type,
                    trigger_config=trigger_config
                )
                logger.info(f"已加载定时任务: {name} ({job_id})")
            
            except Exception as e:
                logger.error(f"加载任务失败 {job_id}: {e}")
        
        conn.close()
    
    def _add_scheduler_job(
        self,
        job_id: str,
        tool_id: str,
        args_json: str,
        trigger_type: str,
        trigger_config: str
    ):
        """添加任务到调度器"""
        config = json.loads(trigger_config)
        
        # 创建触发器
        if trigger_type == "cron":
            trigger = CronTrigger(**config)
        elif trigger_type == "interval":
            trigger = IntervalTrigger(**config)
        elif trigger_type == "date":
            trigger = DateTrigger(**config)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger_type}")
        
        # 添加到调度器
        self.scheduler.add_job(
            func=self._execute_scheduled_job,
            trigger=trigger,
            id=job_id,
            args=[job_id, tool_id, args_json],
            replace_existing=True
        )
    
    def _execute_scheduled_job(self, job_id: str, tool_id: str, args_json: str):
        """
        执行定时任务
        
        Args:
            job_id: 任务ID
            tool_id: 工具ID
            args_json: 参数JSON
        """
        logger.info(f"执行定时任务: {job_id} -> {tool_id}")
        
        try:
            # 导入执行器（避免循环依赖）
            from automation_hub.simple_executor import SimpleExecutor
            
            executor = SimpleExecutor(self.db_path)
            args = json.loads(args_json)
            
            result = executor.execute_tool(
                tool_id=tool_id,
                args=args,
                user_id=f"scheduler:{job_id}"
            )
            
            # 更新任务执行信息
            self._update_job_stats(
                job_id=job_id,
                success=result.get("success", False)
            )
            
            logger.info(f"定时任务执行完成: {job_id}, 成功: {result.get('success')}")
        
        except Exception as e:
            logger.exception(f"定时任务执行失败: {job_id}")
            self._update_job_stats(job_id=job_id, success=False)
    
    def _update_job_stats(self, job_id: str, success: bool):
        """更新任务统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            UPDATE scheduled_jobs
            SET last_run_at = ?,
                run_count = run_count + 1
            WHERE id = ?
        """, (now, job_id))
        
        conn.commit()
        conn.close()
    
    def create_job(
        self,
        name: str,
        tool_id: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        args: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> str:
        """
        创建定时任务
        
        Args:
            name: 任务名称
            tool_id: 工具ID
            trigger_type: 触发器类型 (cron/interval/date)
            trigger_config: 触发器配置
            args: 工具参数
            created_by: 创建者
            
        Returns:
            任务ID
            
        Examples:
            # Cron表达式
            create_job("每天备份", "backup_notes", "cron", {
                "hour": 2,
                "minute": 0
            })
            
            # 间隔执行
            create_job("每小时检查", "check_status", "interval", {
                "hours": 1
            })
            
            # 单次执行
            create_job("一次性任务", "cleanup", "date", {
                "run_date": "2026-01-23 10:00:00"
            })
        """
        job_id = str(uuid.uuid4())
        args_json = json.dumps(args or {})
        trigger_config_json = json.dumps(trigger_config)
        now = datetime.utcnow().isoformat()
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO scheduled_jobs 
            (id, name, tool_id, args_json, trigger_type, trigger_config, 
             created_by, created_at, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (job_id, name, tool_id, args_json, trigger_type, 
              trigger_config_json, created_by, now))
        
        conn.commit()
        conn.close()
        
        # 添加到调度器
        if self.scheduler.running:
            self._add_scheduler_job(
                job_id=job_id,
                tool_id=tool_id,
                args_json=args_json,
                trigger_type=trigger_type,
                trigger_config=trigger_config_json
            )
        
        logger.info(f"已创建定时任务: {name} ({job_id})")
        
        return job_id
    
    def delete_job(self, job_id: str):
        """删除定时任务"""
        # 从调度器移除
        try:
            self.scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        
        # 从数据库删除
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"已删除定时任务: {job_id}")
    
    def enable_job(self, job_id: str):
        """启用定时任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新数据库
        cursor.execute("""
            UPDATE scheduled_jobs
            SET enabled = 1
            WHERE id = ?
        """, (job_id,))
        
        # 获取任务配置
        cursor.execute("""
            SELECT tool_id, args_json, trigger_type, trigger_config
            FROM scheduled_jobs
            WHERE id = ?
        """, (job_id,))
        
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if row and self.scheduler.running:
            tool_id, args_json, trigger_type, trigger_config = row
            self._add_scheduler_job(
                job_id=job_id,
                tool_id=tool_id,
                args_json=args_json,
                trigger_type=trigger_type,
                trigger_config=trigger_config
            )
        
        logger.info(f"已启用定时任务: {job_id}")
    
    def disable_job(self, job_id: str):
        """禁用定时任务"""
        # 从调度器移除
        try:
            self.scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        
        # 更新数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_jobs
            SET enabled = 0
            WHERE id = ?
        """, (job_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"已禁用定时任务: {job_id}")
    
    def list_jobs(self, enabled_only: bool = False) -> List[ScheduledJob]:
        """列出所有定时任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM scheduled_jobs"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query)
        
        jobs = []
        for row in cursor.fetchall():
            job = ScheduledJob(
                id=row[0],
                name=row[1],
                tool_id=row[2],
                args_json=row[3],
                trigger_type=row[4],
                trigger_config=row[5],
                enabled=bool(row[6]),
                created_by=row[7] or "system",
                created_at=row[8],
                last_run_at=row[9],
                next_run_at=row[10],
                run_count=row[11] or 0
            )
            jobs.append(job)
        
        conn.close()
        
        return jobs
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """获取任务详情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return ScheduledJob(
            id=row[0],
            name=row[1],
            tool_id=row[2],
            args_json=row[3],
            trigger_type=row[4],
            trigger_config=row[5],
            enabled=bool(row[6]),
            created_by=row[7] or "system",
            created_at=row[8],
            last_run_at=row[9],
            next_run_at=row[10],
            run_count=row[11] or 0
        )


def create_example_jobs(db_path: str):
    """创建示例定时任务"""
    scheduler = SchedulerService(db_path)
    
    # 每天凌晨2点备份笔记
    scheduler.create_job(
        name="每日备份笔记",
        tool_id="backup_notes",
        trigger_type="cron",
        trigger_config={"hour": 2, "minute": 0}
    )
    
    # 每小时获取RSS
    scheduler.create_job(
        name="每小时获取RSS",
        tool_id="fetch_rss",
        trigger_type="interval",
        trigger_config={"hours": 1}
    )
    
    # 每天早上9点生成报告
    scheduler.create_job(
        name="每日早报",
        tool_id="daily_report",
        trigger_type="cron",
        trigger_config={"hour": 9, "minute": 0}
    )
    
    # 每周一凌晨清理
    scheduler.create_job(
        name="每周清理",
        tool_id="cleanup_dir",
        trigger_type="cron",
        trigger_config={"day_of_week": "mon", "hour": 3, "minute": 0},
        args={"directory": "./data/runs", "days": 30}
    )
    
    print("✅ 已创建4个示例定时任务")
    
    for job in scheduler.list_jobs():
        print(f"  - {job.name} ({job.trigger_type})")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "examples":
        create_example_jobs("data/automation_hub.sqlite3")
    else:
        print("用法: python scheduler.py examples")
