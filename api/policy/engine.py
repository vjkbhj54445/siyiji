"""策略评估引擎模块。

本模块提供工具执行的策略评估功能，包括：
- 权限范围验证
- 风险级别评估
- 参数 Schema 验证
- 审批流程决策
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import json
import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """工具风险级别枚举。"""
    READ = "read"
    EXEC_LOW = "exec_low"
    EXEC_HIGH = "exec_high"
    WRITE = "write"


class ToolDict(TypedDict, total=False):
    """工具配置类型定义。"""
    id: int
    name: str
    is_enabled: int
    risk_level: str
    args_schema_json: str | None


@dataclass
class Decision:
    """策略决策结果。
    
    Attributes:
        allowed: 是否允许执行
        requires_approval: 是否需要审批
        reason: 决策原因说明
    """
    allowed: bool
    requires_approval: bool
    reason: str = ""


# 需要审批的风险级别
APPROVAL_REQUIRED_RISKS = {RiskLevel.EXEC_HIGH, RiskLevel.WRITE}


@lru_cache(maxsize=128)
def _parse_schema(schema_json: str | None) -> dict[str, Any]:
    """解析并缓存 JSON Schema。
    
    Args:
        schema_json: JSON Schema 字符串
        
    Returns:
        解析后的 schema 字典，解析失败返回空字典
    """
    if not schema_json:
        return {}
    
    try:
        return json.loads(schema_json)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse tool schema: {e}")
        return {}


def _validate_schema(args: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, str]:
    """验证参数是否符合 JSON Schema。
    
    Args:
        args: 待验证的参数
        schema: JSON Schema 定义
        
    Returns:
        (是否通过验证, 错误信息)
    """
    if not schema:
        return True, ""
    
    try:
        # 尝试导入 jsonschema，如果不存在则跳过验证
        import jsonschema
        jsonschema.validate(instance=args, schema=schema)
        return True, ""
    except ImportError:
        logger.debug("jsonschema not installed, skipping schema validation")
        return True, ""
    except jsonschema.ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    except Exception as e:
        logger.error(f"Unexpected error during schema validation: {e}")
        return False, f"Validation error: {str(e)}"


def decide_execute(scopes: list[str], tool: ToolDict, args: dict[str, Any]) -> Decision:
    """评估工具执行请求的策略决策。
    
    Args:
        scopes: 用户权限范围列表
        tool: 工具配置信息
        args: 工具执行参数
        
    Returns:
        Decision: 策略决策结果
        
    Examples:
        >>> tool = {"id": 1, "name": "test", "is_enabled": 1, "risk_level": "exec_low"}
        >>> decision = decide_execute(["tool:execute"], tool, {})
        >>> decision.allowed
        True
    """
    # 1. 检查权限范围
    if "tool:execute" not in scopes:
        return Decision(
            allowed=False,
            requires_approval=False,
            reason="missing required scope: tool:execute"
        )
    
    # 2. 检查工具是否启用
    if int(tool.get("is_enabled", 1)) != 1:
        return Decision(
            allowed=False,
            requires_approval=False,
            reason="tool is disabled"
        )
    
    # 3. 评估风险级别
    risk_level_str = tool.get("risk_level", RiskLevel.EXEC_LOW.value)
    try:
        risk_level = RiskLevel(risk_level_str)
    except ValueError:
        logger.warning(f"Unknown risk level: {risk_level_str}, defaulting to exec_low")
        risk_level = RiskLevel.EXEC_LOW
    
    # 高风险操作需要审批
    if risk_level in APPROVAL_REQUIRED_RISKS:
        return Decision(
            allowed=True,
            requires_approval=True,
            reason=f"risk_level={risk_level.value} requires approval"
        )
    
    # 4. 验证参数 Schema
    schema = _parse_schema(tool.get("args_schema_json"))
    is_valid, validation_error = _validate_schema(args, schema)
    
    if not is_valid:
        return Decision(
            allowed=False,
            requires_approval=False,
            reason=validation_error
        )
    
    # 5. 默认允许执行
    return Decision(
        allowed=True,
        requires_approval=False,
        reason="policy check passed"
    )
