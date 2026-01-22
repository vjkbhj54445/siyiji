"""模块说明：脚本管理接口。"""

from fastapi import APIRouter, HTTPException
from typing import List
import os
import json

from api.db import get_scripts, get_script_by_name, create_script
from api.models import Script, ScriptDetail

router = APIRouter()


@router.get("/", response_model=List[Script])
async def list_scripts():
    """获取所有脚本"""
    scripts = get_scripts()
    return [Script(name=s['name'], description=s['description'], created_at=s['created_at']) for s in scripts]


@router.get("/{script_name}", response_model=ScriptDetail)
async def get_script(script_name: str):
    """获取特定脚本详情"""
    script = get_script_by_name(script_name)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # 从manifest.json获取脚本参数信息
    manifest_path = os.path.join("scripts", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        script_detail = next((s for s in manifest if s['name'] == script_name), None)
        if script_detail:
            return ScriptDetail(
                name=script['name'],
                description=script['description'],
                parameters=script_detail.get('parameters', []),
                created_at=script['created_at']
            )
    
    # 如果没有在manifest中找到，返回基本信息
    return ScriptDetail(
        name=script['name'],
        description=script['description'],
        parameters=[],
        created_at=script['created_at']
    )


@router.post("/")
async def register_script(script: Script):
    """注册新脚本"""
    # 检查脚本文件是否存在
    script_path = os.path.join("scripts", script.name)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script file {script.name} does not exist")
    
    success = create_script(script.name, script.description)
    if not success:
        raise HTTPException(status_code=400, detail="Script already exists")
    
    return {"message": "Script registered successfully"}