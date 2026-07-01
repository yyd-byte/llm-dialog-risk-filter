"""Tests for rule-based detection."""

import pytest
from src.decision.models import Evidence, DetectionSource, RiskCategory


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

    def test_reload(self, rule_detector):
        """Reload should not crash."""
        rule_detector.reload()  # Should not raise