"""Integration tests for funNLP-based variant detection."""

import pytest
import yaml
from pathlib import Path

from src.detection.normalizer import TextNormalizer, NormalizerConfig


def load_yaml_map(path: str) -> dict[str, str]:
    """Load a YAML mapping file, returning empty dict on failure."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(k): str(v) for k, v in (data or {}).items()}


def build_full_normalizer() -> TextNormalizer:
    """Build a TextNormalizer with all funNLP configs loaded."""
    ts_map = load_yaml_map("config/traditional_simplified.yaml")
    abbr_map = load_yaml_map("config/abbreviation_map.yaml")
    decomp_map = load_yaml_map("config/decomposition_map.yaml")
    bypass_map = load_yaml_map("config/bypass_variants.yaml")
    confusable_map = load_yaml_map("config/confusable_chars.yaml")
    pinyin_map = load_yaml_map("config/pinyin_variants.yaml")

    cfg = NormalizerConfig(
        normalize_traditional=True,
        traditional_simplified_map=ts_map,
        normalize_abbreviations=True,
        abbreviation_map=abbr_map,
        normalize_decomposition=True,
        decomposition_map=decomp_map,
        normalize_bypass=True,
        bypass_map=bypass_map,
        normalize_confusable_chars=True,
        confusable_map=confusable_map,
        normalize_pinyin=True,
        pinyin_map=pinyin_map,
    )
    return TextNormalizer(cfg)


class TestEndToEndEvasion:
    """End-to-end tests for evasion detection with funNLP data."""

    @pytest.fixture
    def normalizer(self):
        return build_full_normalizer()

    def test_decomposition_evasion_detected(self, normalizer):
        """Text with character decomposition should be detected."""
        # "贝者十甫寸" is the decomposition of "赌博"
        text = "我想玩贝者十甫寸"
        normalized = normalizer.normalize(text)
        # At minimum the normalized text should contain the restored chars
        assert len(normalized.normalized) > 0
        # Check that at least some decomposition was restored
        assert "赌" in normalized.normalized or "博" in normalized.normalized

    def test_abbreviation_reveals_sensitive(self, normalizer):
        """Abbreviation expansion should reveal hidden sensitive content."""
        # "参赌" → "参加赌博"
        result = normalizer.normalize("有人参赌")
        assert "参加赌博" in result.normalized or "赌博" in result.normalized

    def test_traditional_chinese_normalized(self, normalizer):
        """Traditional Chinese should be converted to simplified."""
        result = normalizer.normalize("這是違禁内容")
        assert "这" in result.normalized

    def test_full_pipeline_no_crash(self, normalizer):
        """Full normalization pipeline should handle mixed evasion text."""
        # Mix of: traditional, bypass, decomposition, abbreviations
        text = "加我薇信玩貝者十甫寸"  # "加我微信玩赌博"
        result = normalizer.normalize(text)
        assert len(result.normalized) > 0
        # Should at minimum normalize 薇信→微信
        assert "微信" in result.normalized

    def test_normal_text_not_broken(self, normalizer):
        """Normal Chinese text should not be corrupted by all these steps."""
        text = "今天天气很好，我想去公园散步"
        result = normalizer.normalize(text)
        assert "今天天气很好" in result.normalized
        assert "公园" in result.normalized
        assert "散步" in result.normalized
