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


class TestEvasionSeparatorStripping:
    """Tests for _strip_evasion_separators."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with separator stripping enabled."""
        return TextNormalizer(NormalizerConfig(strip_evasion_separators=True))

    def test_single_sep_between_isolated_cjk(self, normalizer):
        """Separator between two isolated CJK chars should be removed."""
        result = normalizer.normalize("违/禁")
        assert "/" not in result.normalized
        assert "违禁" in result.normalized

    def test_chain_of_evasion_seps(self, normalizer):
        """Multiple separators in evasion chain should all be removed."""
        result = normalizer.normalize("违/禁/词")
        assert "/" not in result.normalized
        assert result.normalized == "违禁词" or "违禁词" in result.normalized

    def test_pipe_separator_evasion(self, normalizer):
        """Pipe character as evasion separator should be removed."""
        result = normalizer.normalize("色|情")
        assert "|" not in result.normalized

    def test_hyphen_separator_evasion(self, normalizer):
        """Hyphen as evasion separator should be removed."""
        result = normalizer.normalize("赌-博")
        assert "-" not in result.normalized

    def test_normal_separator_between_words_kept(self, normalizer):
        """Separator between multi-character words should be KEPT."""
        result = normalizer.normalize("双肩包/单肩包")
        assert "/" in result.normalized

    def test_normal_slash_in_phrase_kept(self, normalizer):
        """Normal slash usage in Chinese phrase should be kept."""
        result = normalizer.normalize("我想买一个双肩包/单肩包，请告诉我怎么选择")
        assert "/" in result.normalized

    def test_url_slashes_kept(self, normalizer):
        """Slashes in URLs should NOT be removed."""
        result = normalizer.normalize("访问 http://example.com/path 查看")
        assert "http://" in result.normalized

    def test_mixed_cjk_and_english_sep_kept(self, normalizer):
        """Separator between CJK and non-CJK should be kept."""
        result = normalizer.normalize("加微信/QQ")
        assert "/" in result.normalized

    def test_double_char_cjk_evasion(self, normalizer):
        """Two CJK chars with separator between should be removed (evasion)."""
        result = normalizer.normalize("你/好")
        assert "/" not in result.normalized

    def test_dot_separator_evasion(self, normalizer):
        """Dot separator between isolated CJK should be removed."""
        result = normalizer.normalize("色.情")
        assert "." not in result.normalized

    def test_multiple_separator_types(self, normalizer):
        """Mixed separator types in evasion chain should be removed."""
        result = normalizer.normalize("违|禁/词")
        assert "|" not in result.normalized
        assert "/" not in result.normalized

    def test_disabled_separator_stripping(self):
        """When disabled, separators should be kept even in evasion patterns."""
        cfg = NormalizerConfig(strip_evasion_separators=False)
        n = TextNormalizer(cfg)
        result = n.normalize("违/禁")
        assert "/" in result.normalized

    def test_chain_with_multichar_word(self, normalizer):
        """Chain ending at multi-char word: 是///消防员 → 是消防员."""
        result = normalizer.normalize("是///消防员")
        assert "/" not in result.normalized

    def test_many_consecutive_seps(self, normalizer):
        """Many consecutive separators should all be removed."""
        result = normalizer.normalize("违///////禁")
        assert "/" not in result.normalized

    def test_chain_between_single_and_multichar(self, normalizer):
        """Chain connecting isolated char to multi-char word: 色///内容."""
        result = normalizer.normalize("色///内容")
        assert "/" not in result.normalized


class TestConfusableChars:
    """Tests for _normalize_confusable_chars."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with confusable chars enabled and a small test map."""
        test_map = {
            "草": "操",
            "尼": "你",
            "玛": "妈",
        }
        return TextNormalizer(
            NormalizerConfig(
                normalize_confusable_chars=True,
                confusable_map=test_map,
            )
        )

    def test_homophone_replacement(self, normalizer):
        """Homophone character should be replaced with standard form."""
        result = normalizer.normalize("草你妈")
        assert "操" in result.normalized

    def test_multiple_confusable_in_text(self, normalizer):
        """Multiple confusable chars in one text should all be replaced."""
        result = normalizer.normalize("尼玛")
        assert result.normalized == "你妈"

    def test_no_false_positive_on_normal_text(self, normalizer):
        """Normal text without confusable chars should be unchanged (except case)."""
        result = normalizer.normalize("你好世界")
        assert "你好世界" in result.normalized

    def test_disabled_confusable_chars(self):
        """When disabled, confusable chars should not be replaced."""
        test_map = {"草": "操"}
        cfg = NormalizerConfig(
            normalize_confusable_chars=False,
            confusable_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("草你妈")
        assert "草" in result.normalized

    def test_empty_confusable_map(self):
        """Empty confusable map should not crash or modify text."""
        n = TextNormalizer(
            NormalizerConfig(
                normalize_confusable_chars=True,
                confusable_map={},
            )
        )
        result = n.normalize("尼玛")
        assert "尼" in result.normalized
        assert "玛" in result.normalized


class TestTraditionalChinese:
    """Tests for _normalize_traditional_chinese."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with traditional->simplified enabled."""
        test_map = {
            "亂": "乱",
            "倫": "伦",
            "倉": "仓",
            "庫": "库",
        }
        return TextNormalizer(
            NormalizerConfig(
                normalize_traditional=True,
                traditional_simplified_map=test_map,
            )
        )

    def test_traditional_to_simplified(self, normalizer):
        """Traditional characters should be converted to simplified."""
        result = normalizer.normalize("亂倫")
        assert "乱" in result.normalized
        assert "倫" not in result.normalized

    def test_traditional_full_text(self, normalizer):
        """Full traditional text should be converted."""
        result = normalizer.normalize("倉庫")
        assert result.normalized == "仓库" or "仓库" in result.normalized

    def test_mixed_traditional_simplified(self, normalizer):
        """Mixed text should have only traditional chars converted."""
        result = normalizer.normalize("亂伦")
        assert "乱" in result.normalized

    def test_disabled_traditional(self):
        """When disabled, traditional chars should not be converted."""
        test_map = {"亂": "乱"}
        cfg = NormalizerConfig(
            normalize_traditional=False,
            traditional_simplified_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("亂倫")
        assert "亂" in result.normalized

    def test_empty_map(self):
        """Empty traditional map should not crash."""
        n = TextNormalizer(
            NormalizerConfig(
                normalize_traditional=True,
                traditional_simplified_map={},
            )
        )
        result = n.normalize("亂倫")
        assert "亂" in result.normalized


class TestAbbreviationExpansion:
    """Tests for _normalize_abbreviations."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with abbreviation expansion enabled."""
        test_map = {
            "禁毒办": "禁毒办公室",
            "参赌": "参加赌博",
            "禁毒": "禁止毒品",
        }
        return TextNormalizer(
            NormalizerConfig(
                normalize_abbreviations=True,
                abbreviation_map=test_map,
            )
        )

    def test_abbreviation_expansion(self):
        """Known abbreviation should be expanded to full form."""
        test_map = {"高院": "高级人民法院"}
        n = TextNormalizer(
            NormalizerConfig(
                normalize_abbreviations=True,
                abbreviation_map=test_map,
            )
        )
        result = n.normalize("高院判决")
        assert "高级人民法院" in result.normalized
        assert "高院" not in result.normalized

    def test_abbreviation_catches_sensitive_word(self, normalizer):
        """Expanded abbreviation should reveal sensitive keywords."""
        result = normalizer.normalize("有人参赌")
        assert "参加赌博" in result.normalized

    def test_longest_match_priority(self, normalizer):
        """Longer abbreviation should match before shorter substring."""
        result = normalizer.normalize("禁毒办通报")
        assert "禁毒办公室" in result.normalized
        assert "禁止毒品" not in result.normalized

    def test_disabled_abbreviation(self):
        """When disabled, abbreviations should not be expanded."""
        test_map = {"参赌": "参加赌博"}
        cfg = NormalizerConfig(
            normalize_abbreviations=False,
            abbreviation_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("参赌人员")
        assert "参赌" in result.normalized

    def test_empty_map(self):
        """Empty abbreviation map should not crash."""
        n = TextNormalizer(
            NormalizerConfig(
                normalize_abbreviations=True,
                abbreviation_map={},
            )
        )
        result = n.normalize("禁毒办通报")
        assert "禁毒办" in result.normalized


class TestDecompositionRestore:
    """Tests for _normalize_decomposition (Path B)."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with decomposition restoration enabled."""
        test_map = {
            "贝者": "赌",
            "木仓": "枪",
            "丰母": "毒",
        }
        return TextNormalizer(
            NormalizerConfig(
                normalize_decomposition=True,
                decomposition_map=test_map,
            )
        )

    def test_decomposition_restored(self, normalizer):
        """Non-word component combination should be restored."""
        result = normalizer.normalize("玩贝者游戏")
        assert "赌" in result.normalized

    def test_multiple_decompositions(self, normalizer):
        """Multiple decompositions in one text should all be restored."""
        result = normalizer.normalize("贝者博木仓")
        # Both "贝者"→"赌" and "木仓"→"枪" should be restored
        assert "赌" in result.normalized
        assert "枪" in result.normalized

    def test_disabled_decomposition(self):
        """When disabled, decompositions should not be restored."""
        test_map = {"贝者": "赌"}
        cfg = NormalizerConfig(
            normalize_decomposition=False,
            decomposition_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("玩贝者游戏")
        assert "贝者" in result.normalized

    def test_empty_map(self):
        """Empty decomposition map should not crash."""
        n = TextNormalizer(
            NormalizerConfig(
                normalize_decomposition=True,
                decomposition_map={},
            )
        )
        result = n.normalize("贝者博")
        assert "贝者" in result.normalized

    def test_normal_text_unchanged(self, normalizer):
        """Normal Chinese text should not be modified."""
        result = normalizer.normalize("正常的文本内容")
        assert "正常的文本内容" in result.normalized
