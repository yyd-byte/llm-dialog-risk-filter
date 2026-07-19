"""语义模型检测 — 基于嵌入相似度的判断。

支持两种模式：
- local：使用本地 sentence-transformers 模型（默认：BAAI/bge-small-zh-v1.5）。
- api：调用云端嵌入 API（如 SiliconFlow、OpenAI 兼容接口）。

两种模式均计算输入文本与风险类别参考描述之间的余弦相似度，
捕获规则无法确定置信度的模糊情况。
"""

from typing import Optional

import numpy as np

from src.decision.models import Evidence, DetectionSource, RiskCategory, RiskLevel
from src.utils.exceptions import ModelNotAvailableError


# 默认四类风险参考描述，用于向量相似度匹配
DEFAULT_CATEGORY_REFERENCES: dict[str, str] = {
    "sexual": "色情内容、低俗表达、性暗示、性挑逗、不雅词汇、色情服务、裸体",
    "violent": "暴力威胁、人身攻击、自残自杀、恐怖主义、危险行为、伤害他人、杀人",
    "advertising": "广告推广、微信号引流、手机号、外部链接、刷屏营销、拉人加群、加微信",
    "sensitive": "政治敏感、违法信息、谣言传播、破坏社会稳定、危害国家安全、反动",
}

# 参考描述的 BGE 查询前缀（BGE 模型对非对称任务需要加前缀）
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class SemanticDetector:
    """基于嵌入相似度的语义级内容风险检测。

    这是双层过滤架构的第二层，负责处理规则漏检的模糊/规避表达。

    支持两种模式：
    - local（默认）：使用 sentence-transformers 及本地模型。
    - api：使用云端嵌入 API（OpenAI 兼容）。

    属性：
        is_available: 模型/API 是否已加载就绪。
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        confidence_threshold: float = 0.6,
        device: str = "cpu",
        category_references: dict[str, str] | None = None,
        api_mode: bool = False,
        api_config: dict | None = None,
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._category_references = category_references or DEFAULT_CATEGORY_REFERENCES
        self._api_mode = api_mode
        self._api_config = api_config or {}

        # Loaded state
        self._st_model = None       # local: SentenceTransformer instance
        self._api_client = None     # api: EmbeddingAPIClient instance
        self._category_embeddings: dict[str, np.ndarray] = {}
        self._is_loaded = False

    @property
    def is_available(self) -> bool:
        """模型是否已加载就绪。"""
        return self._is_loaded

    def load_model(self) -> None:
        """加载嵌入模型并预计算风险类别嵌入。

        在 local 模式下，从 HuggingFace 下载模型（如未缓存）。
        在 api 模式下，创建 EmbeddingAPIClient 并通过 API 编码参考描述。
        """
        if self._api_mode:
            self._load_api()
        else:
            self._load_local()

    def _load_local(self) -> None:
        """加载本地 sentence-transformers 模型。"""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ModelNotAvailableError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        try:
            self._st_model = SentenceTransformer(
                self.model_name,
                device=self.device,
            )
        except Exception as e:
            raise ModelNotAvailableError(
                f"Failed to load model '{self.model_name}': {e}"
            )

        # Pre-compute embeddings for each risk category reference
        self._category_embeddings = {}
        for category_key, ref_text in self._category_references.items():
            embedding = self._st_model.encode(
                ref_text,
                normalize_embeddings=True,
            )
            self._category_embeddings[category_key] = embedding

        self._is_loaded = True

    def _load_api(self) -> None:
        """初始化云端嵌入 API 客户端并预计算类别嵌入。"""
        from src.llm.embedding_client import EmbeddingAPIClient, EmbeddingConfig

        api_cfg = EmbeddingConfig(
            provider=self._api_config.get("provider", "siliconflow"),
            base_url=self._api_config.get("base_url", "https://api.siliconflow.cn/v1"),
            model=self._api_config.get("model", "BAAI/bge-large-zh-v1.5"),
            api_key=self._api_config.get("api_key", ""),
            timeout=self._api_config.get("timeout", 30),
        )

        if not api_cfg.api_key:
            raise ModelNotAvailableError(
                "API 模式下需要配置 api_key，请在 config/default.yaml 的 "
                "semantic_detection.api.api_key 中填写"
            )

        self._api_client = EmbeddingAPIClient(api_cfg)

        # Pre-compute category embeddings via API
        ref_texts = list(self._category_references.values())
        ref_keys = list(self._category_references.keys())
        try:
            embeddings = self._api_client.encode_batch(ref_texts, normalize=True)
        except Exception as e:
            raise ModelNotAvailableError(
                f"Embedding API 调用失败: {e}"
            )

        self._category_embeddings = dict(zip(ref_keys, embeddings))
        self._is_loaded = True

    def detect(self, text: str) -> list[Evidence]:
        """对文本执行语义检测。

        编码输入文本，计算其与各风险类别参考嵌入的余弦相似度。
        返回相似度超过置信度阈值的类别对应的 Evidence。

        当模型未加载时，返回空列表。
        """
        if not self._is_loaded:
            return []

        if not text.strip():
            return []

        # Encode input text with BGE query prefix for asymmetric matching
        query_text = BGE_QUERY_PREFIX + text
        input_embedding = self._encode(query_text)

        # Map category_key → RiskCategory enum
        category_map = {
            "sexual": RiskCategory.SEXUAL,
            "violent": RiskCategory.VIOLENT,
            "advertising": RiskCategory.ADVERTISING,
            "sensitive": RiskCategory.SENSITIVE,
        }

        evidence_list: list[Evidence] = []
        for category_key, cat_embedding in self._category_embeddings.items():
            similarity = self._cosine_similarity(input_embedding, cat_embedding)

            if similarity >= self.confidence_threshold:
                risk_category = category_map.get(category_key)
                if risk_category is None:
                    continue

                evidence_list.append(Evidence(
                    source=DetectionSource.SEMANTIC,
                    category=risk_category,
                    confidence=round(similarity, 4),
                    matched_pattern=self._category_references.get(category_key, ""),
                    matched_text=text[:100],
                    explanation=(
                        f"语义相似度 {similarity:.2%}，"
                        f"与'{risk_category.value}'类别参考描述高度相似"
                    ),
                ))

        return evidence_list

    def _encode(self, text: str) -> np.ndarray:
        """将文本编码为归一化的嵌入向量。

        根据模式分发到本地模型或 API 客户端。
        """
        if self._api_mode:
            return self._api_client.encode(text, normalize=True)
        else:
            return self._st_model.encode(text, normalize_embeddings=True)

    def detect_with_fallback(self, text: str) -> Optional[Evidence]:
        """执行检测并返回置信度最高的证据，或 None。

        这是为融合层提供的便捷方法。
        """
        evidence_list = self.detect(text)
        if not evidence_list:
            return None
        return max(evidence_list, key=lambda e: e.confidence)

    # ---- Helpers ----

    @staticmethod
    def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """计算两个归一化向量之间的余弦相似度。

        由于两个向量均已 L2 归一化，余弦相似度即为点积。
        """
        return float(np.dot(vec_a, vec_b))