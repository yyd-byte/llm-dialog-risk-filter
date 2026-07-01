"""Tests for desensitization."""

import pytest
from src.decision.models import RiskLevel, RiskResult, Evidence, DetectionSource, RiskCategory
from src.desensitization.desensitizer import Desensitizer, DesensitizeResult


class TestDesensitizer:
    """Tests for Desensitizer."""

    def test_safe_content_not_modified(self, desensitizer):
        """Safe content should be returned as-is."""
        risk = RiskResult(risk_level=RiskLevel.LOW)
        result = desensitizer.desensitize("正常文本", risk)
        assert result.desensitized == "正常文本"
        assert len(result.replaced_fragments) == 0

    def test_high_risk_with_matched_text(self, desensitizer):
        """High risk content with matched fragments should be desensitized."""
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            risk_category=RiskCategory.SENSITIVE,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SENSITIVE,
                    confidence=0.9,
                    matched_pattern="敏感词",
                    matched_text="敏感词",
                    explanation="命中敏感词",
                )
            ]
        )
        result = desensitizer.desensitize("这是敏感词的测试", risk)
        assert "敏感词" not in result.desensitized
        assert len(result.replaced_fragments) > 0

    def test_replacement_preserves_length(self, desensitizer):
        """Replacement should preserve approximate length."""
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            risk_category=RiskCategory.SENSITIVE,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SENSITIVE,
                    confidence=0.9,
                    matched_pattern="敏感词",
                    matched_text="敏感词",
                    explanation="test",
                )
            ]
        )
        result = desensitizer.desensitize("敏感词", risk)
        # With keep_first_last=True, "敏感词" (3 chars) → "敏*词" (3 chars)
        assert len(result.desensitized) == len("敏感词")

    def test_multiple_fragments(self, desensitizer):
        """Multiple matched fragments should all be replaced."""
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SENSITIVE,
                    confidence=0.9,
                    matched_pattern="A",
                    matched_text="A",
                    explanation="test",
                ),
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="B",
                    matched_text="B",
                    explanation="test",
                ),
            ]
        )
        result = desensitizer.desensitize("A和B", risk)
        assert "A" not in result.desensitized and "B" not in result.desensitized
        assert len(result.replaced_fragments) >= 2

    def test_category_label(self, desensitizer):
        """category_label should return Chinese labels."""
        assert "色情" in desensitizer.category_label(RiskCategory.SEXUAL)
        assert "暴力" in desensitizer.category_label(RiskCategory.VIOLENT)
        assert "广告" in desensitizer.category_label(RiskCategory.ADVERTISING)
        assert "敏感" in desensitizer.category_label(RiskCategory.SENSITIVE)