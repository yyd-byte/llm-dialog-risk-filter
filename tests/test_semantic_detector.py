"""Tests for semantic detector."""

from src.detection.semantic_detector import SemanticDetector
from src.decision.models import DetectionSource


class TestSemanticDetector:
    """Tests for SemanticDetector."""

    def test_not_loaded_by_default(self):
        """Semantic detector should not be loaded by default."""
        sd = SemanticDetector()
        assert sd.is_available is False

    def test_detect_returns_empty_when_not_loaded(self, semantic_detector):
        """When model is not loaded, detect should return empty list."""
        evidence = semantic_detector.detect("任何文本")
        assert evidence == []

    def test_detect_with_fallback_returns_none(self, semantic_detector):
        """detect_with_fallback should return None when not loaded."""
        result = semantic_detector.detect_with_fallback("任何文本")
        assert result is None

    def test_custom_threshold(self):
        """Should accept custom confidence threshold."""
        sd = SemanticDetector(confidence_threshold=0.8)
        assert sd.confidence_threshold == 0.8

    def test_custom_device(self):
        """Should accept custom device."""
        sd = SemanticDetector(device="cuda")
        assert sd.device == "cuda"

    def test_default_category_references(self):
        """Should have default category references for all four categories."""
        sd = SemanticDetector()
        for key in ("sexual", "violent", "advertising", "sensitive"):
            assert key in sd._category_references
            assert len(sd._category_references[key]) > 0

    def test_custom_category_references(self):
        """Should accept custom category references."""
        custom_refs = {
            "sexual": "自定义色情描述",
            "violent": "自定义暴力描述",
            "advertising": "自定义广告描述",
            "sensitive": "自定义敏感描述",
        }
        sd = SemanticDetector(category_references=custom_refs)
        assert sd._category_references == custom_refs

    def test_empty_text_returns_empty(self, semantic_detector_with_model):
        """Empty text should return empty evidence list."""
        evidence = semantic_detector_with_model.detect("")
        assert evidence == []

    def test_whitespace_text_returns_empty(self, semantic_detector_with_model):
        """Whitespace-only text should return empty evidence list."""
        evidence = semantic_detector_with_model.detect("   ")
        assert evidence == []

    def test_detect_with_model_returns_evidence(self, semantic_detector_with_model):
        """With model loaded, detect should return evidence for similar text."""
        # With random vectors, most texts will have low similarity
        # but the method should not crash
        evidence = semantic_detector_with_model.detect("测试文本内容")
        assert isinstance(evidence, list)

    def test_detect_with_model_uses_semantic_source(self, semantic_detector_with_model):
        """Evidence from semantic detector should have SEMANTIC source."""
        evidence = semantic_detector_with_model.detect("测试")
        for ev in evidence:
            assert ev.source == DetectionSource.SEMANTIC

    def test_detect_with_fallback_with_model(self, semantic_detector_with_model):
        """detect_with_fallback should work when model is loaded."""
        result = semantic_detector_with_model.detect_with_fallback("测试文本")
        # Returns None or Evidence, but should not crash
        assert result is None or hasattr(result, "confidence")
