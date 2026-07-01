"""Tests for text normalization."""

import pytest
from src.detection.normalizer import TextNormalizer, NormalizerConfig, NormalizedText


class TestTextNormalizer:
    """Tests for TextNormalizer."""

    def test_default_config(self):
        """Normalizer should create with default config."""
        n = TextNormalizer()
        assert n.config.lowercase is True
        assert n.config.full_to_half is True

    def test_custom_config(self):
        """Normalizer should accept custom config."""
        cfg = NormalizerConfig(lowercase=False, full_to_half=False)
        n = TextNormalizer(cfg)
        assert n.config.lowercase is False
        assert n.config.full_to_half is False

    def test_normalize_returns_normalized_text(self, normalizer):
        """Normalize should return NormalizedText with original and normalized."""
        result = normalizer.normalize("Hello World")
        assert isinstance(result, NormalizedText)
        assert result.original == "Hello World"
        assert result.normalized is not None

    def test_lowercase(self, normalizer):
        """Should convert to lowercase."""
        result = normalizer.normalize("Hello WORLD")
        assert result.normalized == "hello world"

    def test_full_to_half(self, normalizer):
        """Should convert full-width to half-width."""
        result = normalizer.normalize("Ｈｅｌｌｏ")
        assert result.normalized == "hello"

    def test_full_width_space(self, normalizer):
        """Full-width space (U+3000) should become regular space."""
        result = normalizer.normalize("你好　世界")
        assert "　" not in result.normalized

    def test_whitespace_collapse(self, normalizer):
        """Multiple spaces should collapse to single."""
        result = normalizer.normalize("hello    world")
        assert result.normalized == "hello world"

    def test_reduce_repeats(self, normalizer):
        """Repeated characters should be reduced."""
        result = normalizer.normalize("aaaaaa")
        assert len(result.normalized) <= 3 + 1  # "aaa" + possible extra

    def test_normalize_empty_string(self, normalizer):
        """Empty string should not crash."""
        result = normalizer.normalize("")
        assert result.normalized == ""

    def test_normalize_chinese(self, normalizer):
        """Chinese text should be handled correctly."""
        result = normalizer.normalize("你好世界！Hello！")
        assert "hello" in result.normalized
        assert "你好世界" in result.normalized


class TestNormalizerConfig:
    """Tests for NormalizerConfig."""

    def test_disable_lowercase(self):
        """Lowercase should be skippable."""
        cfg = NormalizerConfig(lowercase=False)
        n = TextNormalizer(cfg)
        result = n.normalize("HELLO")
        assert result.normalized == "HELLO"

    def test_disable_reduce_repeats(self):
        """Repeat reduction should be skippable."""
        cfg = NormalizerConfig(reduce_repeated_chars=False)
        n = TextNormalizer(cfg)
        result = n.normalize("aaaaaa")
        assert "aaaaaa" in result.normalized