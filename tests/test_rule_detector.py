"""Tests for rule-based detection."""

from src.decision.models import DetectionSource, Evidence, RiskCategory, RiskLevel
from src.detection.rule_detector import RuleDetector
from src.rules.models import Rule


class TestRuleDetector:
    """Tests for RuleDetector."""

    def test_keyword_match(self, rule_detector):
        """Should detect keyword matches."""
        evidence = rule_detector.detect("这是一段包含违规词的文本")
        assert len(evidence) > 0
        assert any(e.matched_pattern == "违规词" for e in evidence)

    def test_regex_match(self, rule_detector):
        """Should detect regex matches."""
        evidence = rule_detector.detect("这是违规123号的内容")
        assert len(evidence) > 0
        assert any(e.matched_pattern == r"违规\d+号" for e in evidence)

    def test_no_match_normal_text(self, rule_detector):
        """Should not match normal text."""
        evidence = rule_detector.detect("今天天气真好")
        assert len(evidence) == 0

    def test_empty_text(self, rule_detector):
        """Should handle empty text."""
        evidence = rule_detector.detect("")
        assert len(evidence) == 0

    def test_evidence_structure(self, rule_detector):
        """Evidence should have correct structure."""
        evidence = rule_detector.detect("违规词")
        assert len(evidence) > 0
        ev = evidence[0]
        assert isinstance(ev, Evidence)
        assert ev.source == DetectionSource.RULE
        assert ev.confidence > 0

    def test_multiple_matches(self, rule_detector):
        """Should detect multiple rules in one text."""
        evidence = rule_detector.detect("违规词和广告测试都出现了")
        assert len(evidence) >= 2

    def test_case_insensitive_keyword(self, rule_detector):
        """Keyword matching should be case-insensitive (handled by normalizer)."""
        # The detector receives already-normalized text
        evidence = rule_detector.detect("违规词")  # already normalized
        assert len(evidence) > 0

    def test_rule_levels_have_distinct_confidence(self, rule_detector):
        """Rule evidence should preserve and score every declared risk level."""
        evidence = rule_detector.detect("违规词 广告测试 低风险甲")
        by_level = {item.declared_risk_level: item for item in evidence}

        assert by_level[RiskLevel.HIGH].confidence == 1.0
        assert by_level[RiskLevel.MEDIUM].confidence == 0.58
        assert by_level[RiskLevel.LOW].confidence == 0.2
        assert by_level[RiskLevel.LOW].step == "rule"

    def test_automaton_preserves_rule_order_with_regex(self, rule_detector):
        """Evidence should keep YAML rule order instead of text occurrence order."""
        evidence = rule_detector.detect("广告测试 违规123号 违规词")
        assert [item.metadata["rule_id"] for item in evidence] == [
            "test-kw-001",
            "test-re-001",
            "test-kw-002",
        ]

    def test_repeated_keyword_emits_one_evidence(self, rule_detector):
        """Repeated input occurrences should still produce one signal per rule."""
        evidence = rule_detector.detect("违规词 违规词 违规词")
        matched = [item for item in evidence if item.metadata["rule_id"] == "test-kw-001"]
        assert len(matched) == 1

    def test_overlapping_keywords_all_match(self, rule_manager):
        """Overlapping configured keywords should each emit one evidence item."""
        rule_manager.add_rule(
            Rule(
                id="overlap-short",
                pattern="风险甲",
                category=RiskCategory.SENSITIVE,
                risk_level=RiskLevel.LOW,
            )
        )
        rule_manager.add_rule(
            Rule(
                id="overlap-long",
                pattern="风险甲乙",
                category=RiskCategory.SENSITIVE,
                risk_level=RiskLevel.LOW,
            )
        )
        detector = RuleDetector(rule_manager)
        evidence = detector.detect("风险甲乙")
        ids = {item.metadata["rule_id"] for item in evidence}
        assert {"overlap-short", "overlap-long"} <= ids

    def test_reload(self, rule_detector):
        """Reload should not crash."""
        rule_detector.reload()  # Should not raise
