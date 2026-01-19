from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/automation_hub.sqlite3")
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """初始化数据库表"""
    with get_db_connection() as conn:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
        conn.commit()


def get_scripts() -> List[Dict[str, Any]]:
    """获取所有脚本"""
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM scripts ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]


def get_script_by_name(name: str) -> Optional[Dict[str, Any]]:
    """根据名称获取脚本"""
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM scripts WHERE name = ?', (name,)).fetchone()
        return dict(row) if row else None


def create_script(name: str, description: str) -> bool:
    """创建新脚本"""
    try:
        with get_db_connection() as conn:
            conn.execute(
                'INSERT INTO scripts (name, description) VALUES (?, ?)',
                (name, description)
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False  # 脚本已存在


def get_tasks() -> List[Dict[str, Any]]:
    """获取所有任务"""
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]


def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取任务"""
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        return dict(row) if row else None


def create_task(name: str, script_name: str, parameters: str = None, scheduled_time=None) -> int:
    """创建新任务"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            '''INSERT INTO tasks (name, script_name, parameters, scheduled_time) 
               VALUES (?, ?, ?, ?)''',
            (name, script_name, parameters, scheduled_time)
        )
        conn.commit()
        return cursor.lastrowid


def update_task_status(task_id: int, status: str):
    """更新任务状态"""
    with get_db_connection() as conn:
        conn.execute(
            '''UPDATE tasks SET status = ?, completed_at = CASE 
               WHEN ? IN ('completed', 'failed') THEN datetime('now') 
               ELSE completed_at END 
               WHERE id = ?''',
            (status, status, task_id)
        )
        conn.commit()


def get_runs() -> List[Dict[str, Any]]:
    """获取所有运行记录"""
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM runs ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]


def get_run_by_id(run_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取运行记录"""
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
        return dict(row) if row else None


def create_run(run_id: str, script_name: str, parameters: str = None) -> bool:
    """创建新的运行记录"""
    try:
        with get_db_connection() as conn:
            conn.execute(
                '''INSERT INTO runs (run_id, script_name, parameters, status) 
                   VALUES (?, ?, ?, ?)''',
                (run_id, script_name, parameters, 'queued')
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def update_run_status(run_id: str, status: str, started: bool = False, completed: bool = False, 
                     result: str = None, error_msg: str = None):
    """更新运行记录状态"""
    with get_db_connection() as conn:
        sql = '''UPDATE runs SET status = ?'''
        params = [status]
        
        if started:
            sql += ', started_at = datetime("now")'
        if completed:
            sql += ', completed_at = datetime("now")'
        if result is not None:
            sql += ', result = ?'
            params.append(result)
        if error_msg is not None:
            sql += ', error_msg = ?'
            params.append(error_msg)
            
        sql += ' WHERE run_id = ?'
        params.append(run_id)
        
        conn.execute(sql, params)
        conn.commit()
