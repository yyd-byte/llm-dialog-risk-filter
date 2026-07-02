"""LLM Client — wrapper for Ollama / OpenAI-compatible API."""

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from src.utils.exceptions import LLMServiceError


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    provider: str = "openai"  # "openai" | "ollama"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    api_key: str = ""
    timeout: int = 30
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """Response from LLM call."""

    text: str
    model: str
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""


class LLMClient:
    """Unified LLM client supporting Ollama and OpenAI-compatible APIs."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = httpx.Client(timeout=self.config.timeout)

    def chat(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Send a chat completion request.

        Args:
            prompt: The user message.
            system_prompt: Optional system instruction.

        Returns:
            LLMResponse with the generated text.
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
        """Call Ollama API."""
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
        """Call OpenAI-compatible API."""
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
        """Close the HTTP client."""
        self._client.close()