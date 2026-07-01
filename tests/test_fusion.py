"""Tests for risk fusion."""

import pytest
from src.decision.models import (
    RiskLevel, RiskCategory, RiskResult, Evidence, DetectionSource
)
from src.decision.fusion import RiskFusion, FusionConfig


class TestRiskFusion:
    """Tests for RiskFusion."""

    def test_empty_evidence_returns_low(self, fusion):
        """No evidence should result in LOW risk."""
        result = fusion.evaluate([], [])
        assert result.risk_level == RiskLevel.LOW
        assert result.is_safe is True

    def test_high_confidence_rule_returns_high(self, fusion):
        """High confidence rule evidence should return HIGH."""
        evidence = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.SENSITIVE,
                confidence=0.9,
                matched_pattern="test",
                matched_text="test",
                explanation="test",
            )
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.HIGH

    def test_medium_confidence_returns_medium(self, fusion):
        """Medium confidence should return MEDIUM."""
        evidence = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.ADVERTISING,
                confidence=0.5,
                matched_pattern="test",
                matched_text="test",
                explanation="test",
            )
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.MEDIUM

    def test_low_confidence_returns_low(self, fusion):
        """Low confidence should return LOW."""
        evidence = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.SENSITIVE,
                confidence=0.1,
                matched_pattern="test",
                matched_text="test",
                explanation="test",
            )
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.LOW

    def test_rule_and_semantic_combined(self, fusion):
        """Rule + semantic evidence should be weighted together."""
        rule_ev = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.SENSITIVE,
                confidence=0.4,
                matched_pattern="kw",
                matched_text="kw",
                explanation="keyword match",
            )
        ]
        sem_ev = [
            Evidence(
                source=DetectionSource.SEMANTIC,
                category=RiskCategory.SENSITIVE,
                confidence=0.8,
                matched_pattern="",
                matched_text="",
                explanation="semantic match",
            )
        ]
        result = fusion.evaluate(rule_ev, sem_ev)
        # Weighted: 0.5*0.4 + 0.5*0.8 = 0.6 → MEDIUM
        assert result.risk_level == RiskLevel.MEDIUM
        assert len(result.evidence_chain) == 2

    def test_evidence_summary(self, fusion):
        """evidence_summary should return readable string."""
        result = RiskResult(risk_level=RiskLevel.LOW)
        summary = fusion.evidence_summary(result)
        assert "正常" in summary or "LOW" in summary

    def test_evaluate_input_same_as_evaluate(self, fusion):
        """evaluate_input should give same result as evaluate."""
        evidence = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.VIOLENT,
                confidence=0.95,
                matched_pattern="x",
                matched_text="x",
                explanation="x",
            )
        ]
        r1 = fusion.evaluate(evidence, [])
        r2 = fusion.evaluate_input(evidence, [])
        assert r1.risk_level == r2.risk_level

    def test_evaluate_output(self, fusion):
        """evaluate_output should work."""
        result = fusion.evaluate_output([], [])
        assert result.risk_level == RiskLevel.LOW

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        cfg = FusionConfig(high_threshold=0.95, medium_threshold=0.8)
        fusion = RiskFusion(cfg)
        evidence = [
            Evidence(
                source=DetectionSource.RULE,
                category=RiskCategory.SENSITIVE,
                confidence=0.9,
                matched_pattern="x",
                matched_text="x",
                explanation="x",
            )
        ]
        result = fusion.evaluate(evidence, [])
        # 0.9 < 0.95 high threshold, but > 0.8 medium → MEDIUM
        assert result.risk_level == RiskLevel.MEDIUM