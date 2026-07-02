"""Semantic model detection — embedding similarity-based judgment.

Uses a lightweight Chinese embedding model to compute similarity between
input text and risk category descriptions, catching ambiguous cases that
rules cannot confidently determine.
"""

from typing import Optional

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
    """Semantic-level content risk detection using embedding similarity.

    This is the second layer of the dual-filter architecture, responsible
    for handling ambiguous/evasive expressions that rules miss.

    Uses a Chinese embedding model (default: BAAI/bge-small-zh-v1.5) to
    compute cosine similarity between input text and risk category reference
    descriptions. Categories exceeding the confidence threshold produce
    Evidence entries.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        confidence_threshold: float = 0.6,
        device: str = "cpu",
        category_references: dict[str, str] | None = None,
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._category_references = category_references or DEFAULT_CATEGORY_REFERENCES

        # Loaded state
        self._st_model = None
        self._category_embeddings: dict[str, "Tensor"] = {}  # noqa: F821
        self._is_loaded = False

    @property
    def is_available(self) -> bool:
        """Whether a real model is loaded and ready."""
        return self._is_loaded

    def load_model(self) -> None:
        """Load the embedding model and pre-compute risk category embeddings.

        Downloads the model from HuggingFace if not already cached locally.
        """
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

    def detect(self, text: str) -> list[Evidence]:
        """Run semantic detection on text.

        Encodes the input text and computes cosine similarity against
        each risk category's reference embedding. Returns Evidence for
        categories whose similarity exceeds the confidence threshold.

        When model is not loaded, returns an empty list.
        """
        if not self._is_loaded:
            return []

        if not text.strip():
            return []

        # Encode input text with BGE query prefix for asymmetric matching
        query_text = BGE_QUERY_PREFIX + text
        input_embedding = self._st_model.encode(
            query_text,
            normalize_embeddings=True,
        )

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

    def detect_with_fallback(self, text: str) -> Optional[Evidence]:
        """Run detection and return the highest-confidence evidence, or None.

        This is a convenience method for the fusion layer.
        """
        evidence_list = self.detect(text)
        if not evidence_list:
            return None
        return max(evidence_list, key=lambda e: e.confidence)

    # ---- Helpers ----

    @staticmethod
    def _cosine_similarity(vec_a, vec_b) -> float:
        """Compute cosine similarity between two normalized vectors.

        Since both vectors are already L2-normalized, cosine similarity
        is simply the dot product.
        """
        import numpy as np
        return float(np.dot(vec_a, vec_b))