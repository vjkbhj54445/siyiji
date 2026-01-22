"""OpenAI 兼容 LLM 客户端（无需额外依赖）。"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class OpenAICompatibleClient:
    """OpenAI 兼容接口客户端。

    环境变量:
    - OPENAI_API_KEY
    - OPENAI_BASE_URL (默认 https://api.openai.com/v1)
    - OPENAI_MODEL (默认 gpt-4o-mini)
    """

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 60

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (self.base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = self.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 未设置")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发起 chat completion 请求（返回原始 JSON 响应）。"""

        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        def _post() -> Dict[str, Any]:
            url = f"{self.base_url}/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()

        return await asyncio.to_thread(_post)


def extract_content(response: Any) -> str:
    """从不同响应结构中提取文本内容。"""
    if isinstance(response, str):
        return response
    if isinstance(response, bytes):
        return response.decode("utf-8", errors="ignore")

    # OpenAI 风格 dict
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"]
        except Exception:
            return json.dumps(response, ensure_ascii=False)

    # OpenAI SDK 风格对象
    if hasattr(response, "choices"):
        try:
            return response.choices[0].message.content
        except Exception:
            pass

    return str(response)
