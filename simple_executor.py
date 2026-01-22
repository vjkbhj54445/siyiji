"""
简单执行器 - 不依赖AI，直接连接数据库和Worker

用于非AI场景的工具执行
"""

import sqlite3
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SimpleExecutor:
    """简单执行器 - 直接执行工具，无需Agent规划"""
    
    def __init__(self, db_path: str):
        """
        初始化执行器
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
    
    def execute_tool(
        self,
        tool_id: str,
        args: Dict[str, Any],
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        执行工具（同步版本）
        
        Args:
            tool_id: 工具ID
            args: 工具参数
            user_id: 用户ID
            
        Returns:
            执行结果字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 1. 检查工具是否存在且已启用
            cursor.execute("""
                SELECT id, name, risk_level, executor, command_json, 
                       args_schema_json, timeout_seconds
                FROM tools
                WHERE id = ? AND enabled = 1
            """, (tool_id,))
            
            tool = cursor.fetchone()
            
            if not tool:
                return {
                    "success": False,
                    "error": f"工具不存在或未启用: {tool_id}"
                }
            
            tool_id, name, risk_level, executor, command_json, args_schema_json, timeout_seconds = tool
            
            # 2. 创建run记录
            run_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            cursor.execute("""
                INSERT INTO runs (id, tool_id, args_json, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, tool_id, json.dumps(args), "queued", now))
            
            # 3. 检查是否需要审批
            if risk_level in ["exec_high", "write"]:
                # 创建审批请求
                approval_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO approval_requests 
                    (id, resource_type, resource_id, requested_by, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (approval_id, "run", run_id, user_id, "pending", now))
                
                conn.commit()
                
                logger.info(f"工具 {tool_id} 需要审批，approval_id: {approval_id}")
                
                return {
                    "success": False,
                    "run_id": run_id,
                    "approval_id": approval_id,
                    "status": "pending_approval",
                    "message": f"工具 {name} 需要审批（风险级别: {risk_level}）"
                }
            
            # 4. 直接执行（低风险工具）
            conn.commit()
            
            # 更新状态为running
            cursor.execute("""
                UPDATE runs SET status = 'running', started_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), run_id))
            conn.commit()
            
            # 5. 实际执行命令
            result = self._execute_command(
                command_json=command_json,
                args=args,
                timeout=timeout_seconds
            )
            
            # 6. 更新执行结果
            cursor.execute("""
                UPDATE runs
                SET status = ?, stdout = ?, stderr = ?, exit_code = ?, completed_at = ?
                WHERE id = ?
            """, (
                "succeeded" if result["exit_code"] == 0 else "failed",
                result.get("stdout", ""),
                result.get("stderr", ""),
                result["exit_code"],
                datetime.utcnow().isoformat(),
                run_id
            ))
            
            conn.commit()
            
            # 7. 记录审计日志
            cursor.execute("""
                INSERT INTO audit_events 
                (event_type, actor_user_id, resource_type, resource_id, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "run.executed",
                user_id,
                "run",
                run_id,
                "success" if result["exit_code"] == 0 else "fail",
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            
            return {
                "success": result["exit_code"] == 0,
                "run_id": run_id,
                "status": "succeeded" if result["exit_code"] == 0 else "failed",
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result["exit_code"]
            }
        
        except Exception as e:
            logger.exception(f"执行工具失败: {tool_id}")
            
            # 记录失败
            if 'run_id' in locals():
                cursor.execute("""
                    UPDATE runs
                    SET status = 'failed', stderr = ?, completed_at = ?
                    WHERE id = ?
                """, (str(e), datetime.utcnow().isoformat(), run_id))
                conn.commit()
            
            return {
                "success": False,
                "error": str(e)
            }
        
        finally:
            conn.close()
    
    def _execute_command(
        self,
        command_json: str,
        args: Dict[str, Any],
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        执行命令
        
        Args:
            command_json: 命令模板（JSON）
            args: 参数
            timeout: 超时时间
            
        Returns:
            执行结果
        """
        import subprocess
        
        try:
            # 解析命令模板
            command_template = json.loads(command_json)
            
            # 替换参数
            command = []
            for part in command_template:
                # 简单的参数替换（可以改进）
                if part.startswith("{") and part.endswith("}"):
                    param_name = part[1:-1]
                    if param_name in args:
                        command.append(str(args[param_name]))
                else:
                    command.append(part)
            
            # 添加剩余参数
            for key, value in args.items():
                placeholder = f"{{{key}}}"
                if placeholder not in command_template:
                    # 参数未在模板中，添加为额外参数
                    if isinstance(value, bool):
                        if value:
                            command.append(f"--{key}")
                    else:
                        command.append(str(value))
            
            logger.info(f"执行命令: {' '.join(command)}")
            
            # 执行
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}秒）"
            }
        
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"命令执行失败: {str(e)}"
            }
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            run_id: 任务ID
            
        Returns:
            任务状态信息
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT r.id, r.tool_id, t.name, r.status, r.stdout, r.stderr, 
                       r.exit_code, r.created_at, r.started_at, r.completed_at
                FROM runs r
                LEFT JOIN tools t ON r.tool_id = t.id
                WHERE r.id = ?
            """, (run_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "run_id": row[0],
                "tool_id": row[1],
                "tool_name": row[2],
                "status": row[3],
                "stdout": row[4],
                "stderr": row[5],
                "exit_code": row[6],
                "created_at": row[7],
                "started_at": row[8],
                "completed_at": row[9]
            }
        
        finally:
            conn.close()
