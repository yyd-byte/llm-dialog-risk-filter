"""Tests for risk fusion."""

import pytest

from src.decision.fusion import FusionConfig, RiskFusion, fusion_config_from_dict
from src.decision.models import DetectionSource, Evidence, RiskCategory, RiskLevel, RiskResult


def rule_evidence(
    text: str,
    level: RiskLevel,
    category: RiskCategory = RiskCategory.SENSITIVE,
) -> Evidence:
    """Build synthetic rule evidence without using production vocabulary."""
    scores = {RiskLevel.LOW: 0.2, RiskLevel.MEDIUM: 0.58, RiskLevel.HIGH: 1.0}
    return Evidence(
        source=DetectionSource.RULE,
        category=category,
        confidence=scores[level],
        matched_text=text,
        declared_risk_level=level,
    )


def semantic_evidence(score: float, category: RiskCategory = RiskCategory.SENSITIVE) -> Evidence:
    """Build synthetic semantic evidence."""
    return Evidence(source=DetectionSource.SEMANTIC, category=category, confidence=score)


class TestRiskFusion:
    """Tests for category-aware severity-aware fusion."""

    def test_empty_evidence_returns_low(self, fusion):
        """No evidence should result in LOW risk."""
        result = fusion.evaluate([], [])
        assert result.risk_level == RiskLevel.LOW
        assert result.is_safe is True

    def test_single_low_rule_stays_low(self, fusion):
        """One low rule should not cause an intervention."""
        result = fusion.evaluate([rule_evidence("low-one", RiskLevel.LOW)], [])
        assert result.risk_level == RiskLevel.LOW
        assert result.confidence == pytest.approx(0.2)

    def test_three_distinct_low_rules_escalate_to_medium(self, fusion):
        """Three independent low signals in one category should escalate."""
        evidence = [
            rule_evidence("low-one", RiskLevel.LOW),
            rule_evidence("low-two", RiskLevel.LOW),
            rule_evidence("low-three", RiskLevel.LOW),
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.confidence == pytest.approx(0.488)

    def test_duplicate_low_rule_does_not_escalate(self, fusion):
        """Repeated evidence for one fragment should count only once."""
        evidence = [
            rule_evidence("low-one", RiskLevel.LOW),
            rule_evidence("LOW-ONE", RiskLevel.LOW),
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.LOW
        assert result.confidence == pytest.approx(0.2)

    def test_low_signals_from_different_categories_do_not_compound(self, fusion):
        """Weak signals in separate policy categories should not aggregate."""
        evidence = [
            rule_evidence("low-one", RiskLevel.LOW, RiskCategory.SENSITIVE),
            rule_evidence("low-two", RiskLevel.LOW, RiskCategory.ADVERTISING),
            rule_evidence("low-three", RiskLevel.LOW, RiskCategory.VIOLENT),
        ]
        result = fusion.evaluate(evidence, [])
        assert result.risk_level == RiskLevel.LOW
        assert result.confidence == pytest.approx(0.2)

    def test_medium_rule_returns_medium(self, fusion):
        """One medium rule should require desensitization."""
        result = fusion.evaluate([rule_evidence("medium", RiskLevel.MEDIUM)], [])
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.confidence == pytest.approx(0.58)

    def test_high_rule_overrides_other_evidence(self, fusion):
        """A high rule should remain a direct block signal."""
        result = fusion.evaluate(
            [rule_evidence("high", RiskLevel.HIGH)],
            [semantic_evidence(0.1)],
        )
        assert result.risk_level == RiskLevel.HIGH
        assert result.confidence == 1.0

    def test_semantic_only_confidence_is_not_attenuated(self, fusion):
        """Semantic-only evidence should not be weighted against an absent rule source."""
        result = fusion.evaluate([], [semantic_evidence(0.8)])
        assert result.risk_level == RiskLevel.HIGH
        assert result.confidence == pytest.approx(0.8)

    def test_rule_and_semantic_combined(self, fusion):
        """Evidence from both sources should use normalized configured weights."""
        result = fusion.evaluate(
            [rule_evidence("medium", RiskLevel.MEDIUM)],
            [semantic_evidence(0.8)],
        )
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.confidence == pytest.approx(0.69)

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        fusion = RiskFusion(FusionConfig(high_threshold=0.95, medium_threshold=0.8))
        result = fusion.evaluate([rule_evidence("medium", RiskLevel.MEDIUM)], [])
        assert result.risk_level == RiskLevel.LOW

    def test_invalid_rule_confidence_is_rejected(self):
        """Invalid severity ordering should fail fast."""
        with pytest.raises(ValueError, match="rule confidence"):
            FusionConfig(
                rule_confidence={
                    RiskLevel.LOW: 0.6,
                    RiskLevel.MEDIUM: 0.5,
                    RiskLevel.HIGH: 1.0,
                }
            )

    def test_yaml_compatible_config_maps_levels(self):
        """Configuration loader should accept YAML string keys."""
        config = fusion_config_from_dict(
            {
                "rule_confidence": {"low": 0.1, "medium": 0.5, "high": 1.0},
            }
        )
        assert config.rule_confidence[RiskLevel.LOW] == 0.1

    def test_evidence_summary(self, fusion):
        """evidence_summary should return readable string."""
        summary = fusion.evidence_summary(RiskResult(risk_level=RiskLevel.LOW))
        assert "正常" in summary or "LOW" in summary
