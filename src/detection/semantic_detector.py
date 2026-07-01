"""Semantic model detection — ML-based secondary judgment.

Uses a lightweight text classification model to handle ambiguous cases
that rules cannot confidently determine.
"""

from typing import Optional

from src.decision.models import Evidence, DetectionSource, RiskCategory, RiskLevel
from src.utils.exceptions import ModelNotAvailableError


class SemanticDetector:
    """Semantic-level content risk detection using ML model.

    This is the second layer of the dual-filter architecture, responsible
    for handling ambiguous/evasive expressions that rules miss.

    Initially uses a heuristic/simulation mode. When a real model is loaded
    via load_model(), it switches to actual inference.
    """

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese",
                 confidence_threshold: float = 0.6,
                 device: str = "cpu"):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._model = None
        self._tokenizer = None
        self._is_loaded = False

    @property
    def is_available(self) -> bool:
        """Whether a real model is loaded and ready."""
        return self._is_loaded

    def load_model(self) -> None:
        """Load the pretrained model into memory.

        Downloads the model if not already cached locally.
        """
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )
            self._model.to(self.device)
            self._model.eval()
            self._is_loaded = True
        except ImportError:
            raise ModelNotAvailableError(
                "transformers/torch not installed. "
                "Install with: pip install transformers torch"
            )
        except Exception as e:
            raise ModelNotAvailableError(f"Failed to load model '{self.model_name}': {e}")

    def detect(self, text: str) -> list[Evidence]:
        """Run semantic detection on text.

        When model is not loaded, returns empty list (no semantic evidence).
        When model is loaded, runs inference and returns evidence for
        detected risks.
        """
        if not self._is_loaded:
            return []

        # TODO: Real model inference
        # For now, return empty — real implementation will:
        # 1. Tokenize text
        # 2. Run model inference
        # 3. Map output to RiskCategory + confidence
        # 4. Return Evidence list
        return []

    def detect_with_fallback(self, text: str) -> Optional[Evidence]:
        """Run detection and return the highest-confidence evidence, or None.

        This is a convenience method for the fusion layer.
        """
        evidence_list = self.detect(text)
        if not evidence_list:
            return None
        return max(evidence_list, key=lambda e: e.confidence)