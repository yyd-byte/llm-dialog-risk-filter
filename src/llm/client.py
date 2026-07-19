"""大模型客户端 — 统一的对话补全接口，支持 Ollama 和 OpenAI 兼容 API。"""

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from src.utils.exceptions import LLMServiceError


@dataclass
class LLMConfig:
    """LLM 客户端配置 — 提供商、地址、模型、密钥和调用参数。"""

    provider: str = "openai"  # "openai" | "ollama"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    api_key: str = ""
    timeout: int = 30
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """LLM 调用响应 — 生成文本、模型名称、耗时和状态信息。"""

    text: str
    model: str
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""


class LLMClient:
    """统一的大模型对话客户端。

    支持两种后端：
    - ollama: 本地 Ollama 服务
    - openai: 任意 OpenAI 兼容 API（DeepSeek / 通义千问 / 智谱等）
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = httpx.Client(timeout=self.config.timeout)

    def chat(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """发送对话补全请求。

        Args:
            prompt: 用户输入的提示文本。
            system_prompt: 可选的系统指令。

        Returns:
            包含生成文本的 LLMResponse。
        """
        start = time.time()

        if self.config.provider == "ollama":
            return self._ollama_chat(prompt, system_prompt, start)
        elif self.config.provider == "openai":
            return self._openai_chat(prompt, system_prompt, start)
        else:
            raise LLMServiceError(f"Unknown LLM provider: {self.config.provider}")

    def _ollama_chat(self, prompt: str, system_prompt: str,
                     start: float) -> LLMResponse:
        """通过 Ollama 本地 API 发送对话请求。

        Args:
            prompt: 用户输入的提示文本。
            system_prompt: 可选的系统指令。
            start: 请求开始时间戳（用于计算耗时）。

        Returns:
            包含生成文本或错误信息的 LLMResponse。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = self._client.post(
                f"{self.config.base_url}/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "num_predict": self.config.max_tokens,
                        "temperature": self.config.temperature,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                text=data["message"]["content"],
                model=self.config.model,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return LLMResponse(
                text="",
                model=self.config.model,
                duration_ms=(time.time() - start) * 1000,
                success=False,
                error=str(e),
            )

    def _openai_chat(self, prompt: str, system_prompt: str,
                     start: float) -> LLMResponse:
        """通过 OpenAI 兼容 API（DeepSeek 等）发送对话请求。

        使用 httpx 发送 POST 请求，自动处理超时和错误响应。

        Args:
            prompt: 用户输入的提示文本。
            system_prompt: 可选的系统指令。
            start: 请求开始时间戳（用于计算耗时）。

        Returns:
            包含生成文本或错误信息的 LLMResponse。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            resp = self._client.post(
                f"{self.config.base_url}/v1/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                text=data["choices"][0]["message"]["content"],
                model=self.config.model,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return LLMResponse(
                text="",
                model=self.config.model,
                duration_ms=(time.time() - start) * 1000,
                success=False,
                error=str(e),
            )

    def close(self) -> None:
        """关闭 HTTP 客户端，释放连接资源。"""
        self._client.close()