"""云端 Embedding API 客户端 — 将文本转换为向量表示。

支持 OpenAI 兼容的 Embedding API（如 SiliconFlow），
用于语义检测层的文本向量化和相似度计算。
"""

from dataclasses import dataclass

import httpx
import numpy as np


@dataclass
class EmbeddingConfig:
    """Embedding API 客户端配置 — 提供商、地址、模型和密钥。"""

    provider: str = "siliconflow"
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "BAAI/bge-large-zh-v1.5"
    api_key: str = ""
    timeout: int = 30


class EmbeddingAPIClient:
    """OpenAI 兼容 Embedding API 的轻量级客户端。

    用法:
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
        """将单条文本编码为嵌入向量。

        Args:
            text: 待编码的输入文本。
            normalize: 若为 True，对输出向量进行 L2 归一化。

        Returns:
            shape 为 (dim,) 的 numpy 数组。
        """
        embeddings = self.encode_batch([text], normalize=normalize)
        return embeddings[0]

    def encode_batch(self, texts: list[str], normalize: bool = True) -> list[np.ndarray]:
        """批量编码多条文本为嵌入向量。

        Args:
            texts: 待编码的文本列表。
            normalize: 若为 True，对输出向量进行 L2 归一化。

        Returns:
            numpy 数组列表，每个数组 shape 为 (dim,)。
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
            raise RuntimeError(f"Embedding API 调用失败 ({self.config.provider}): {e}") from e

    def close(self) -> None:
        """关闭 HTTP 客户端，释放连接资源。"""
        self._client.close()

    @property
    def is_available(self) -> bool:
        """检查 API 客户端是否已配置有效凭证。"""
        return bool(self.config.api_key)
