import json
import os
from typing import List, Dict, Any, Optional, Generator

import requests


class OpenAICompatClient:
    """通用 OpenAI 兼容接口客户端，支持不同 provider（如 SiliconFlow、豆包等）的 /chat/completions 调用"""
    def __init__(
        self,
        api_base: str,
        api_key: str,
        default_model: str,
        request_timeout: int = 60,
        default_params: Optional[Dict[str, Any]] = None,
    ):
        self.api_base = (api_base or "").rstrip("/")
        self.api_key = api_key or ""
        self.default_model = default_model
        self.request_timeout = int(request_timeout or 60)
        self.default_params = default_params or {}
        if not self.api_base:
            raise RuntimeError("api_base 未配置")
        if not self.api_key:
            raise RuntimeError("api_key 未配置")
        if not self.default_model:
            raise RuntimeError("default_model 未配置")

    def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """非流式聊天完成"""
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
        }
        if self.default_params:
            payload.update(self.default_params)
        if extra_params:
            payload.update(extra_params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.request_timeout)
        resp.raise_for_status()
        return resp.json()

    def chat_completions_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """流式聊天完成，返回内容片段生成器"""
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
        }
        if self.default_params:
            payload.update(self.default_params)
        if extra_params:
            payload.update(extra_params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        with requests.post(url, headers=headers, json=payload, timeout=self.request_timeout, stream=True) as resp:
            resp.raise_for_status()
            resp.encoding = 'utf-8'  # 确保正确的编码
            
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.strip():
                    continue
                    
                # 处理 SSE 格式
                if line.startswith('data: '):
                    data_str = line[6:]  # 移除 'data: ' 前缀
                    
                    # 检查是否是结束标记
                    if data_str.strip() == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        # 忽略无法解析的行
                        continue

