"""Embedding API Client — OpenAI-compatible embedding service wrapper.

Supports cloud embedding APIs (SiliconFlow, OpenAI, etc.) as an alternative
to local sentence-transformers models.
"""

from dataclasses import dataclass

import httpx
import numpy as np


@dataclass
class EmbeddingConfig:
    """Configuration for embedding API client."""

    provider: str = "siliconflow"
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "BAAI/bge-large-zh-v1.5"
    api_key: str = ""
    timeout: int = 30


class EmbeddingAPIClient:
    """Lightweight client for OpenAI-compatible embedding APIs.

    Usage:
        client = EmbeddingAPIClient(EmbeddingConfig(
            base_url="https://api.siliconflow.cn/v1",
            model="BAAI/bge-large-zh-v1.5",
            api_key="sk-xxx",
        ))
        vec = client.encode("你好世界")
        vecs = client.encode_batch(["文本1", "文本2"])
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or EmbeddingConfig()
        self._client = httpx.Client(timeout=self.config.timeout)

    def encode(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text to an embedding vector.

        Args:
            text: Input text to encode.
            normalize: If True, L2-normalize the output vector.

        Returns:
            numpy array of shape (dim,).
        """
        embeddings = self.encode_batch([text], normalize=normalize)
        return embeddings[0]

    def encode_batch(
        self, texts: list[str], normalize: bool = True
    ) -> list[np.ndarray]:
        """Encode multiple texts to embedding vectors.

        Args:
            texts: List of input texts.
            normalize: If True, L2-normalize the output vectors.

        Returns:
            List of numpy arrays, each of shape (dim,).
        """
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            resp = self._client.post(
                f"{self.config.base_url}/embeddings",
                json={
                    "model": self.config.model,
                    "input": texts,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            vectors = []
            for item in data["data"]:
                vec = np.array(item["embedding"], dtype=np.float32)
                if normalize:
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                vectors.append(vec)

            return vectors

        except Exception as e:
            raise RuntimeError(
                f"Embedding API 调用失败 ({self.config.provider}): {e}"
            ) from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    @property
    def is_available(self) -> bool:
        """Check if the API client is configured with credentials."""
        return bool(self.config.api_key)