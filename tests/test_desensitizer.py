"""Tests for desensitization."""

import pytest
from src.decision.models import RiskLevel, RiskResult, Evidence, DetectionSource, RiskCategory
from src.desensitization.desensitizer import (
    Desensitizer, DesensitizeConfig, DesensitizeResult, DEFAULT_SEMANTIC_LABELS,
)


class TestDesensitizerMaskMode:
    """Tests for legacy mask-mode desensitization (*** replacement)."""

    @pytest.fixture
    def desensitizer(self):
        return Desensitizer(DesensitizeConfig(mode="mask"))

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


class TestDesensitizerSemanticMode:
    """Tests for semantic-mode desensitization (category labels)."""

    @pytest.fixture
    def desensitizer(self):
        return Desensitizer(DesensitizeConfig(mode="semantic"))

    def test_sexual_replaced_with_label(self, desensitizer):
        """Sexual fragment should be replaced with [不雅用语]."""
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            risk_category=RiskCategory.SEXUAL,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SEXUAL,
                    confidence=0.9,
                    matched_pattern="裸聊",
                    matched_text="裸聊",
                    explanation="命中色情词",
                )
            ]
        )
        result = desensitizer.desensitize("加我QQ裸聊", risk)
        assert "[不雅用语]" in result.desensitized
        assert "裸聊" not in result.desensitized

    def test_advertising_replaced_with_label(self, desensitizer):
        """Advertising fragment should be replaced with [联系方式]."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.ADVERTISING,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="微信号abc123",
                    matched_text="微信号abc123",
                    explanation="命中广告词",
                )
            ]
        )
        result = desensitizer.desensitize("请加我微信号abc123谢谢", risk)
        assert "[联系方式]" in result.desensitized
        assert "微信号abc123" not in result.desensitized

    def test_sentence_structure_preserved(self, desensitizer):
        """After semantic replacement, sentence structure should remain readable."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.ADVERTISING,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="加微信",
                    matched_text="加微信",
                    explanation="命中广告词",
                )
            ]
        )
        result = desensitizer.desensitize("有问题可以加微信联系我", risk)
        # Should be: "有问题可以[联系方式]联系我" — LLM can understand this
        assert "[联系方式]" in result.desensitized
        assert "联系我" in result.desensitized  # surrounding text preserved

    def test_violent_replaced_with_label(self, desensitizer):
        """Violent fragment should be replaced with [暴力用语]."""
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            risk_category=RiskCategory.VIOLENT,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.VIOLENT,
                    confidence=0.9,
                    matched_pattern="杀了你",
                    matched_text="杀了你",
                    explanation="命中暴力词",
                )
            ]
        )
        result = desensitizer.desensitize("我要杀了你", risk)
        assert "[暴力用语]" in result.desensitized

    def test_unknown_category_uses_fallback(self):
        """Evidence with a category not in labels map should use fallback."""
        cfg = DesensitizeConfig(
            mode="semantic",
            category_labels={},  # empty → falls back for all categories
        )
        d = Desensitizer(cfg)
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SENSITIVE,
                    confidence=0.9,
                    matched_pattern="something",
                    matched_text="something",
                    explanation="test",
                )
            ]
        )
        result = d.desensitize("something bad", risk)
        assert "[违规内容]" in result.desensitized

    def test_safe_content_not_modified_semantic(self, desensitizer):
        """Safe content should still be returned as-is in semantic mode."""
        risk = RiskResult(risk_level=RiskLevel.LOW)
        result = desensitizer.desensitize("正常文本", risk)
        assert result.desensitized == "正常文本"

    def test_custom_labels(self):
        """Custom category labels should override defaults."""
        cfg = DesensitizeConfig(
            mode="semantic",
            category_labels={"sexual": "[色情]", "advertising": "[广告]"},
        )
        d = Desensitizer(cfg)
        risk = RiskResult(
            risk_level=RiskLevel.HIGH,
            risk_category=RiskCategory.SEXUAL,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SEXUAL,
                    confidence=0.9,
                    matched_pattern="bad",
                    matched_text="bad",
                    explanation="test",
                )
            ]
        )
        result = d.desensitize("bad word", risk)
        assert "[色情]" in result.desensitized


class TestDesensitizerCommon:
    """Tests that apply regardless of mode."""

    def test_category_label(self):
        """category_label should return Chinese labels."""
        d = Desensitizer()
        assert "色情" in d.category_label(RiskCategory.SEXUAL)
        assert "暴力" in d.category_label(RiskCategory.VIOLENT)
        assert "广告" in d.category_label(RiskCategory.ADVERTISING)
        assert "敏感" in d.category_label(RiskCategory.SENSITIVE)

    def test_default_mode_is_semantic(self):
        """Default config should use semantic mode."""
        d = Desensitizer()
        assert d.config.mode == "semantic"


class TestDesensitizerRewriteMode:
    """Tests for rewrite-mode desensitization (LLM naturalization)."""

    @pytest.fixture
    def desensitizer(self):
        return Desensitizer(DesensitizeConfig(mode="rewrite"))

    def test_rewrite_falls_back_to_semantic_without_llm(self, desensitizer):
        """Without llm_call, rewrite mode should fall back to semantic labels."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.ADVERTISING,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="加微信", matched_text="加微信",
                    explanation="命中广告词",
                )
            ]
        )
        result = desensitizer.desensitize("加微信聊聊", risk)  # no llm_call
        assert "[联系方式]" in result.desensitized
        assert not result.was_rewritten

    def test_rewrite_with_mock_llm(self, desensitizer):
        """With llm_call, rewrite mode should naturalize the text."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.ADVERTISING,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="加微信", matched_text="加微信",
                    explanation="命中广告词",
                )
            ]
        )

        def mock_llm(prompt: str) -> str:
            # Simulate LLM rewriting [联系方式]聊聊 → 私下聊
            return "想私下聊"

        result = desensitizer.desensitize("加微信聊聊", risk, llm_call=mock_llm)
        assert result.was_rewritten
        assert "私下" in result.desensitized

    def test_rewrite_makes_semantic_replacement_first(self, desensitizer):
        """Rewrite mode should first do semantic replacement, then LLM rewrite."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.SEXUAL,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.SEXUAL,
                    confidence=0.8,
                    matched_pattern="裸聊", matched_text="裸聊",
                    explanation="命中色情词",
                )
            ]
        )

        captured_prompt = []

        def mock_llm(prompt: str) -> str:
            captured_prompt.append(prompt)
            return "想视频聊天"

        result = desensitizer.desensitize("加我QQ裸聊吧", risk, llm_call=mock_llm)
        # The prompt sent to LLM should contain the semantic label
        assert len(captured_prompt) == 1
        assert "[不雅用语]" in captured_prompt[0]
        assert result.was_rewritten
        assert "视频聊天" in result.desensitized

    def test_rewrite_with_failing_llm_falls_back(self, desensitizer):
        """If LLM call raises exception, fall back to semantic labels."""
        risk = RiskResult(
            risk_level=RiskLevel.MEDIUM,
            risk_category=RiskCategory.ADVERTISING,
            evidence_chain=[
                Evidence(
                    source=DetectionSource.RULE,
                    category=RiskCategory.ADVERTISING,
                    confidence=0.8,
                    matched_pattern="加微信", matched_text="加微信",
                    explanation="命中广告词",
                )
            ]
        )

        def failing_llm(prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        result = desensitizer.desensitize("加微信聊聊", risk, llm_call=failing_llm)
        # Should fall back to semantic labels without crashing
        assert "[联系方式]" in result.desensitized
        assert not result.was_rewritten
