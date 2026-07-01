"""Tests for semantic detector."""

import pytest
from src.detection.semantic_detector import SemanticDetector


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