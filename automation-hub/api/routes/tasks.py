from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import List
from api.db import get_tasks, get_task_by_id, create_task, update_task_status
from api.models import Task

router = APIRouter()


@router.get("/", response_model=List[Task])
async def list_tasks():
    """获取所有任务"""
    tasks = get_tasks()
    return [
        Task(
            id=t['id'],
            name=t['name'],
            script_name=t['script_name'],
            parameters=t['parameters'],
            status=t['status'],
            created_at=t['created_at'],
            scheduled_time=t['scheduled_time'],
            completed_at=t['completed_at']
        ) for t in tasks
    ]


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int):
    """获取特定任务详情"""
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return Task(
        id=task['id'],
        name=task['name'],
        script_name=task['script_name'],
        parameters=task['parameters'],
        status=task['status'],
        created_at=task['created_at'],
        scheduled_time=task['scheduled_time'],
        completed_at=task['completed_at']
    )


@router.post("/", response_model=Task)
async def create_new_task(task: Task):
    """创建新任务"""
    task_id = create_task(
        name=task.name,
        script_name=task.script_name,
        parameters=task.parameters,
        scheduled_time=task.scheduled_time
    )
    
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    # 返回创建的任务
    created_task = get_task_by_id(task_id)
    return Task(
        id=created_task['id'],
        name=created_task['name'],
        script_name=created_task['script_name'],
        parameters=created_task['parameters'],
        status=created_task['status'],
        created_at=created_task['created_at'],
        scheduled_time=created_task['scheduled_time'],
        completed_at=created_task['completed_at']
    )


@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: int, task: Task):
    """更新任务"""
    existing_task = get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 更新任务状态
    if task.status != existing_task['status']:
        update_task_status(task_id, task.status)
        existing_task['status'] = task.status
    
    return Task(
        id=existing_task['id'],
        name=existing_task['name'],
        script_name=existing_task['script_name'],
        parameters=existing_task['parameters'],
        status=existing_task['status'],
        created_at=existing_task['created_at'],
        scheduled_time=existing_task['scheduled_time'],
        completed_at=existing_task['completed_at']
    )


@router.delete("/{task_id}")
async def delete_task(task_id: int):
    """删除任务（暂时不实现，只是标记为取消）"""
    existing_task = get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_task_status(task_id, "cancelled")
    return {"message": "Task cancelled successfully"}
