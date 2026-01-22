"""
Agent API 路由

提供自然语言交互接口
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
import logging
import asyncio

from api.config import settings
from automation_hub.agent import (
    AgentPlanner,
    AgentExecutor,
    ConversationContext,
    OpenAICompatibleClient,
    StepStatus,
)
from api.db import (
    create_tool_run,
    get_tool_run_by_id,
    update_tool_run_status,
)
from api.tools.registry import get_tool
from api.approvals.service import create_approval

import redis
from rq import Queue

from worker.jobs_v2 import run_tool_job

# TODO: 导入认证依赖（需要实际实现）
# from ..auth.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ==================== 内部状态 ====================

_SESSION_STORE: Dict[str, ConversationContext] = {}
_RUN_STORE: Dict[str, Dict[str, Any]] = {}
_LLM_CLIENT: Optional[OpenAICompatibleClient] = None


def _get_llm_client() -> OpenAICompatibleClient:
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        _LLM_CLIENT = OpenAICompatibleClient()
    return _LLM_CLIENT


def _get_context(session_id: str, user_id: str) -> ConversationContext:
    ctx = _SESSION_STORE.get(session_id)
    if ctx is None:
        ctx = ConversationContext(user_id=user_id, session_id=session_id)
        _SESSION_STORE[session_id] = ctx
    return ctx


def _apply_extra_context(ctx: ConversationContext, extra: Optional[dict]) -> None:
    if not extra:
        return
    cwd = extra.get("cwd") or extra.get("working_directory")
    files = extra.get("recent_files")
    project_type = extra.get("project_type")
    ctx.update_working_context(cwd=cwd, files=files, project_type=project_type)
    preferences = extra.get("preferences")
    if isinstance(preferences, dict):
        for k, v in preferences.items():
            ctx.set_preference(k, v)
    variables = extra.get("variables")
    if isinstance(variables, dict):
        for k, v in variables.items():
            ctx.set_variable(k, v)


class _LocalRunClient:
    """工具执行客户端：落库到 tool_runs，并通过 RQ 入队 worker.jobs_v2.run_tool_job。"""

    def __init__(self):
        redis_conn = redis.from_url(settings.REDIS_URL)
        name = (settings.QUEUE_NAME.split(",", 1)[0] or "default").strip()
        self.queue = Queue(name, connection=redis_conn)

    def _requires_approval(self, risk_level: str) -> bool:
        return risk_level in {"write", "exec_high"}

    async def create_run(self, tool_id: str, args: dict, user_id: str) -> Dict[str, Any]:
        tool = get_tool(tool_id)
        if not tool or not int(tool.get("is_enabled", 1)):
            raise ValueError(f"tool not found: {tool_id}")

        run_id = str(uuid.uuid4())

        # 输出文件路径
        from pathlib import Path

        run_dir = Path(settings.RUNS_DIR) / "tool_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = str(run_dir / "stdout.txt")
        stderr_path = str(run_dir / "stderr.txt")

        risk_level = tool.get("risk_level", "exec_low")
        approval_id: str | None = None
        status = "queued"

        if self._requires_approval(risk_level):
            status = "pending_approval"
            approval_id = create_approval(
                user_id=user_id,
                device_id=None,
                resource_type="run",
                resource_id=run_id,
                action="execute",
                risk_level=risk_level,
                reason=f"execute tool {tool_id}",
                payload={"tool_id": tool_id, "args": args, "run_id": run_id},
            )

        ok = create_tool_run(
            run_id=run_id,
            tool_id=tool_id,
            args=args,
            status=status,
            created_by_user_id=user_id,
            approval_request_id=approval_id,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if not ok:
            raise RuntimeError("failed to create tool run")

        if status == "queued":
            self.queue.enqueue(
                run_tool_job,
                run_id=run_id,
                tool_id=tool_id,
                args=args,
                user_id=user_id,
                job_timeout=int(tool.get("timeout_sec") or 120) + 30,
            )
            return {"run_id": run_id, "status": "queued"}

        return {"run_id": run_id, "status": "pending_approval", "approval_id": approval_id}

    async def get_run_status(self, run_id: str) -> Dict[str, Any]:
        r = get_tool_run_by_id(run_id)
        if not r:
            return {"status": "failed", "error": "run not found"}
        status = r.get("status")
        if status == "succeeded":
            return {"status": "succeeded", "output": "ok"}
        if status in {"failed", "denied"}:
            return {"status": status, "error": r.get("error_msg") or "failed"}
        if status == "pending_approval":
            return {"status": "pending_approval", "approval_id": r.get("approval_request_id")}
        return {"status": status}


# ==================== 请求/响应模型 ====================

class AskRequest(BaseModel):
    """询问请求"""
    query: str = Field(description="用户自然语言输入", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, description="会话ID（可选，用于保持上下文）")
    context: Optional[dict] = Field(default=None, description="额外上下文信息")


class AskResponse(BaseModel):
    """询问响应"""
    plan_id: str = Field(description="执行计划ID")
    summary: str = Field(description="执行结果摘要")
    status: str = Field(description="执行状态: success|partial|failed|blocked")
    steps_completed: int = Field(description="完成的步骤数")
    total_steps: int = Field(description="总步骤数")
    session_id: str = Field(description="会话ID")
    execution_time: float = Field(description="总执行时间（秒）")
    pending_approvals: List[str] = Field(default_factory=list, description="待审批 ID 列表（当 status=blocked 时）")


class PlanRequest(BaseModel):
    """仅规划请求（不执行）"""
    query: str = Field(description="用户自然语言输入")
    session_id: Optional[str] = None
    context: Optional[dict] = Field(default=None, description="额外上下文信息")


class PlanResponse(BaseModel):
    """规划响应"""
    plan_id: str
    task_type: str
    steps: List[dict]
    estimated_duration: int


class ExecutePlanRequest(BaseModel):
    """执行已有计划"""
    plan_id: str = Field(description="计划ID")


# ==================== API 端点 ====================

@router.post("/ask", response_model=AskResponse)
async def agent_ask(
    request: AskRequest,
    # user = Depends(get_current_user)  # TODO: 启用认证
):
    """
    Agent 主入口 - 自然语言询问
    
    流程:
    1. 解析意图并生成计划
    2. 执行计划
    3. 返回结果
    
    示例:
    ```json
    {
      "query": "搜索所有 TODO 注释",
      "session_id": "optional-session-id"
    }
    ```
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        user_id = "system"

        llm_client = _get_llm_client()
        planner = AgentPlanner(llm_client, db_path=str(settings.DATABASE_PATH))
        executor = AgentExecutor(api_client=_LocalRunClient())

        context = _get_context(session_id=session_id, user_id=user_id)
        _apply_extra_context(context, request.context)

        context.add_message("user", request.query)
        plan = await planner.plan(request.query, context)
        result = await executor.execute_plan(plan, user_id=user_id)
        context.add_message("assistant", result.summary)

        steps_completed = len([r for r in result.step_results if r.status == StepStatus.COMPLETED])
        total_steps = len(result.step_results)
        pending_approvals = [r.approval_id for r in result.step_results if getattr(r, "approval_id", None)]

        return AskResponse(
            plan_id=result.plan_id,
            summary=result.summary,
            status=result.status,
            steps_completed=steps_completed,
            total_steps=total_steps,
            session_id=session_id,
            execution_time=result.total_duration,
            pending_approvals=pending_approvals,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("处理询问时出错")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    request: PlanRequest,
    # user = Depends(get_current_user)
):
    """
    仅生成计划（不执行）
    
    用于预览 Agent 将执行的操作
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        user_id = "system"

        llm_client = _get_llm_client()
        planner = AgentPlanner(llm_client, db_path=str(settings.DATABASE_PATH))

        context = _get_context(session_id=session_id, user_id=user_id)
        _apply_extra_context(context, request.context)

        plan = await planner.plan(request.query, context)

        return PlanResponse(
            plan_id=plan.plan_id,
            task_type=plan.task_type.value,
            steps=[step.dict() for step in plan.steps],
            estimated_duration=plan.estimated_duration
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成计划时出错")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成计划失败: {str(e)}"
        )


@router.post("/execute/{plan_id}")
async def execute_plan(
    plan_id: str,
    # user = Depends(get_current_user)
):
    """
    执行已生成的计划
    
    配合 /plan 端点使用，实现"预览-确认-执行"流程
    """
    try:
        # TODO: 实际实现
        # 1. 从存储中获取计划
        # 2. 验证计划属于当前用户
        # 3. 执行计划
        # 4. 返回结果
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="此功能尚未实现"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("执行计划时出错")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行计划失败: {str(e)}"
        )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    # user = Depends(get_current_user)
):
    """
    获取会话上下文
    
    用于查看对话历史和上下文信息
    """
    try:
        # TODO: 从存储中加载会话上下文
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="此功能尚未实现"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取会话时出错")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话失败: {str(e)}"
        )
