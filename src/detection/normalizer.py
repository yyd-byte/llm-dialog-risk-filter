"""Text normalization — handles evasion techniques before detection."""

import re
from dataclasses import dataclass, field


# ---- CJK character detection ----

# Common CJK Unicode ranges
_CJK_RANGES = [
    (0x4E00, 0x9FFF),     # CJK Unified Ideographs (常用汉字)
    (0x3400, 0x4DBF),     # CJK Unified Ideographs Extension A
    (0xF900, 0xFAFF),     # CJK Compatibility Ideographs
]


def _is_cjk(ch: str) -> bool:
    """Check if character is a CJK (Chinese/Japanese/Korean) ideograph."""
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _contains_cjk(s: str) -> bool:
    """Check if string contains at least one CJK character."""
    return any(_is_cjk(ch) for ch in s)


def _replace_ascii_boundary(text: str, variant: str,
                            replacement: str) -> str:
    """Replace `variant` with `replacement` only at token boundaries.

    A token boundary is: start-of-string, end-of-string, whitespace,
    punctuation, CJK character, or symbol — anything that is NOT a
    letter or digit.  This prevents "bc" matching inside "abc123".
    """
    if variant not in text:
        return text
    # Build a regex that matches `variant` only when surrounded by
    # non-alphanumeric characters (or string boundaries).
    # Use lookbehind/lookahead to ensure we don't consume the boundaries.
    pattern = r'(?<![a-zA-Z0-9])' + re.escape(variant) + r'(?![a-zA-Z0-9])'
    return re.sub(pattern, replacement, text)


# ---- Separator characters commonly used for keyword evasion ----

# Characters that are inserted between CJK characters to evade keyword matching.
# Includes ASCII punctuation and Chinese punctuation marks.
_EVASION_SEPARATORS = frozenset(
    "/|\\-_*.,·•～~!#^&+=;；，、。，．"
)


@dataclass
class NormalizerConfig:
    """Configuration for TextNormalizer."""

    lowercase: bool = True
    full_to_half: bool = True
    normalize_whitespace: bool = True
    reduce_repeated_chars: bool = True
    max_repeat: int = 3
    normalize_symbols: bool = True
    normalize_bypass: bool = True
    bypass_map: dict[str, str] = field(default_factory=dict)
    # New: strip evasion separators between isolated single CJK chars
    strip_evasion_separators: bool = True
    # New: normalize confusable characters (形近字/同音字)
    normalize_confusable_chars: bool = True
    confusable_map: dict[str, str] = field(default_factory=dict)
    # New: pinyin-aware normalization (requires pypinyin for dynamic mode)
    normalize_pinyin: bool = True
    pinyin_map: dict[str, str] = field(default_factory=dict)
    # New: traditional Chinese -> simplified Chinese
    normalize_traditional: bool = True
    traditional_simplified_map: dict[str, str] = field(default_factory=dict)
    # New: abbreviation expansion
    normalize_abbreviations: bool = True
    abbreviation_map: dict[str, str] = field(default_factory=dict)
    # New: character decomposition restoration (Path B)
    normalize_decomposition: bool = True
    decomposition_map: dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizedText:
    """Result of text normalization."""

    original: str
    normalized: str
    # Position mapping: normalized index → original index (approximate)
    position_map: list[int] = field(default_factory=list)


class TextNormalizer:
    """Pre-processes text before detection to handle evasion techniques.

    Handles: full/half-width conversion, case normalization, whitespace
    normalization, bypass variant normalization (homophones, similar-looking
    characters, pinyin, etc.), repeated character compression, evasion
    separator stripping, confusable character normalization, and symbol
    normalization.
    """

    def __init__(self, config: NormalizerConfig | None = None):
        self.config = config or NormalizerConfig()

    def normalize(self, text: str) -> NormalizedText:
        """Apply all enabled normalization steps."""
        result = text
        for step in [
            self._normalize_full_to_half,
            self._normalize_traditional_chinese,
            self._normalize_abbreviations,
            self._normalize_decomposition,
            self._normalize_bypass_variants,
            self._normalize_confusable_chars,
            self._normalize_pinyin_variants,
            self._normalize_case,
            self._strip_evasion_separators,
            self._normalize_whitespace,
            self._reduce_repeats,
            self._normalize_symbols,
        ]:
            if self._is_enabled(step.__name__):
                result = step(result)
        return NormalizedText(original=text, normalized=result)

    def _is_enabled(self, step_name: str) -> bool:
        """Check if a normalization step is enabled in config."""
        mapping = {
            "_normalize_full_to_half": self.config.full_to_half,
            "_normalize_case": self.config.lowercase,
            "_normalize_whitespace": self.config.normalize_whitespace,
            "_normalize_bypass_variants": self.config.normalize_bypass,
            "_reduce_repeats": self.config.reduce_repeated_chars,
            "_normalize_symbols": self.config.normalize_symbols,
            "_strip_evasion_separators": self.config.strip_evasion_separators,
            "_normalize_confusable_chars": self.config.normalize_confusable_chars,
            "_normalize_pinyin_variants": self.config.normalize_pinyin,
            "_normalize_traditional_chinese": self.config.normalize_traditional,
            "_normalize_abbreviations": self.config.normalize_abbreviations,
            "_normalize_decomposition": self.config.normalize_decomposition,
        }
        return mapping.get(step_name, True)

    # ---- Individual normalization steps ----

    def _normalize_full_to_half(self, text: str) -> str:
        """Convert full-width characters to half-width.

        Full-width range: FF01-FF5E → half-width 21-7E (offset: FEE0)
        Full-width space: 3000 → 20
        """
        result = []
        for ch in text:
            code = ord(ch)
            if code == 0x3000:
                result.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(ch)
        return "".join(result)

    def _normalize_case(self, text: str) -> str:
        """Convert to lowercase."""
        return text.lower()

    def _normalize_whitespace(self, text: str) -> str:
        """Collapse multiple whitespace characters into single space."""
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_bypass_variants(self, text: str) -> str:
        """Replace known bypass variants with their standard forms.

        Handles: homophones (薇信→微信), similar-looking chars (草你→操你),
        pinyin (weixin→微信), symbol variants (+V→加微信), number codes (419→一夜情).

        Uses word-boundary matching for ASCII entries to prevent false
        positives like "bc" matching inside "abc123".  CJK entries use
        plain substring matching (safe for multi-char CJK phrases).
        """
        if not self.config.bypass_map:
            return text
        str_map = {str(k): str(v) for k, v in self.config.bypass_map.items()}
        for variant in sorted(str_map, key=len, reverse=True):
            replacement = str_map[variant]
            if _contains_cjk(variant):
                # CJK variant: safe to use substring matching
                if variant in text:
                    text = text.replace(variant, replacement)
            else:
                if len(variant) <= 3:
                    # Short ASCII keys (vx, wx, VX etc.): use plain
                    # substring matching so they match adjacent digits
                    # (e.g. "vx123") which boundary matching would miss.
                    if variant in text:
                        text = text.replace(variant, replacement)
                else:
                    # Longer ASCII variant: use word-boundary matching to
                    # avoid matching substrings inside longer alphanumeric
                    # tokens (e.g. "bc" inside "abc123").
                    text = _replace_ascii_boundary(text, variant, replacement)
        return text

    def _normalize_pinyin_variants(self, text: str) -> str:
        """Replace CJK spans whose pinyin matches known sensitive words.

        Uses pypinyin for dynamic CJK→pinyin conversion if available.
        Falls back to direct substring matching for ASCII pinyin in text.

        Example (with pypinyin):
            "加我薇信" → pinyin "jia wo weixin" → matches "weixin" →
            replaces "薇信" with "微信"

        Without pypinyin, ASCII pinyin like "weixin" in mixed text is
        already handled by _normalize_bypass_variants.
        """
        if not self.config.pinyin_map:
            return text

        # Try dynamic CJK→pinyin conversion
        try:
            import pypinyin
            return self._pinyin_cjk_replace(text, self.config.pinyin_map, pypinyin)
        except ImportError:
            pass

        # Fallback: direct ASCII pinyin matching in text
        # (Mostly redundant with bypass_variants, but handles edge cases)
        str_map = {str(k): str(v) for k, v in self.config.pinyin_map.items()}
        for variant in sorted(str_map, key=len, reverse=True):
            if variant in text:
                text = text.replace(variant, str_map[variant])
        return text

    @staticmethod
    def _pinyin_cjk_replace(text: str, pinyin_map: dict[str, str],
                            pypinyin) -> str:
        """Use pypinyin to convert CJK spans to pinyin and replace matches."""
        str_map = {str(k): str(v) for k, v in pinyin_map.items()}
        # Get pinyin for the whole text
        # pypinyin.pinyin returns a list of lists, e.g. [['wo'], ['ai'], ['ni']]
        pinyin_list = pypinyin.lazy_pinyin(text, style=pypinyin.Style.TONE3,
                                           errors='ignore')
        # Build positions: find CJK spans and their pinyin
        n = len(text)
        result = list(text)

        # Sliding window approach: for each CJK span, try matching pinyin
        i = 0
        pinyin_idx = 0  # index into pinyin_list（粗略对应，非CJK字符不计入）
        # Build a mapping from text position to pinyin list index
        pos_to_pinyin: list[int | None] = [None] * n
        pi = 0
        for ti, ch in enumerate(text):
            if _is_cjk(ch) and pi < len(pinyin_list):
                pos_to_pinyin[ti] = pi
                pi += 1

        # Try multi-character CJK spans against pinyin map
        # Start from longest possible spans
        cjk_positions = [ti for ti, pi_val in enumerate(pos_to_pinyin) if pi_val is not None]
        # Sliding window: try spans of CJK chars and check their concatenated pinyin
        for start in range(len(cjk_positions)):
            for end in range(start + 1, min(start + 8, len(cjk_positions) + 1)):
                span_start = cjk_positions[start]
                span_end = cjk_positions[end - 1] + 1
                cjk_span = text[span_start:span_end]
                # Get pinyin for this span
                pinyin_indices = [pos_to_pinyin[i] for i in range(span_start, span_end)
                                  if pos_to_pinyin[i] is not None]
                if not pinyin_indices:
                    continue
                # Build pinyin string
                pinyin_str = ''.join(
                    pinyin_list[idx] for idx in pinyin_indices
                )
                # Remove tone numbers for matching
                pinyin_flat = ''.join(
                    c for c in pinyin_str if not c.isdigit()
                )
                if pinyin_flat in str_map:
                    replacement = str_map[pinyin_flat]
                    # Replace the CJK span
                    result[span_start:span_end] = list(replacement)

        return ''.join(result)

    def _normalize_traditional_chinese(self, text: str) -> str:
        """Convert traditional Chinese characters to simplified.

        Uses the traditional_simplified_map from config, loaded from
        traditional_simplified.yaml.
        """
        if not self.config.traditional_simplified_map:
            return text
        str_map = {str(k): str(v) for k, v
                   in self.config.traditional_simplified_map.items()}
        result = []
        for ch in text:
            result.append(str_map.get(ch, ch))
        return "".join(result)

    def _normalize_abbreviations(self, text: str) -> str:
        """Expand known abbreviations to their full forms.

        Uses longest-match-first to prevent partial matches:
        "禁毒办" should match "禁毒办" not "禁毒" first.

        Only matches Chinese abbreviations (2+ CJK characters) to
        avoid false positives on English acronyms.
        """
        if not self.config.abbreviation_map:
            return text
        str_map = {str(k): str(v) for k, v
                   in self.config.abbreviation_map.items()}

        # Phase 1: replace all matches with unique placeholder markers.
        # This prevents shorter keys from matching inside the replacement
        # text of longer keys (e.g. "禁毒" matching within "禁毒办公室").
        markers: dict[str, str] = {}
        for i, abbr in enumerate(sorted(str_map, key=len, reverse=True)):
            if len(abbr) < 2:
                continue
            if not _contains_cjk(abbr):
                continue
            if abbr in text:
                marker = f"\x00ABBR_{i}\x00"
                markers[marker] = str_map[abbr]
                text = text.replace(abbr, marker)

        # Phase 2: replace placeholders with actual expansions.
        for marker, expansion in markers.items():
            text = text.replace(marker, expansion)
        return text

    def _normalize_decomposition(self, text: str) -> str:
        """Restore decomposed CJK characters (Path B: global with dictionary check).

        Detects patterns where attackers write characters as individual
        components to evade keyword matching. Only reverses when the
        component combination is NOT a real Chinese word (verified via
        jieba's built-in frequency dictionary).

        Example:
            "木仓" → not a real word → "枪" (restored)
            "女子" → real word (woman) → kept as-is
        """
        if not self.config.decomposition_map:
            return text

        str_map = {str(k): str(v) for k, v
                   in self.config.decomposition_map.items()}

        # Build a set of known Chinese words for dictionary validation
        try:
            import jieba
            _known_words: frozenset[str] = frozenset(
                w for w in jieba.dt.FREQ if len(w) >= 2
            )
            _has_dict = True
        except (ImportError, AttributeError):
            _known_words = frozenset()
            _has_dict = False

        result = list(text)
        n = len(text)

        i = 0
        while i < n:
            if n - i < 2:   # remaining text too short for any decomposition
                break
            matched = False
            candidate_len = 1  # default advance when no match
            for window in range(min(5, n - i), 1, -1):
                candidate = text[i:i + window]
                if candidate not in str_map:
                    continue
                original_char = str_map[candidate]

                if _has_dict and candidate in _known_words:
                    # This is a real dictionary word — don't restore
                    # (e.g., "女子" = woman, not "好").
                    # Advance past the entire candidate so we don't
                    # re-process its tail as a false decomposition.
                    matched = False
                    candidate_len = len(candidate)
                elif not _has_dict and len(candidate) == 2:
                    # No dictionary available: 2-char combos are too
                    # risky (most real Chinese words are 2 chars).
                    matched = False
                    candidate_len = len(candidate)
                else:
                    # Not a known word → likely decomposition → restore
                    result[i:i + window] = [original_char]
                    matched = True
                break
            i += window if matched else candidate_len

        return "".join(result)

    def _normalize_confusable_chars(self, text: str) -> str:
        """Replace confusable CJK characters with their standard forms.

        Handles: 形近字 (形→行), 同音字替换 (草→操), etc.
        Uses the confusable_map from config, loaded from confusable_chars.yaml.

        Unlike bypass_variants (phrase-level), this operates at the character
        level — replacing individual confusable characters throughout the text.
        """
        if not self.config.confusable_map:
            return text
        # Sort by key char; since these are single chars, ordering by
        # the character itself is fine (no overlap concerns like with phrases)
        str_map = {str(k): str(v) for k, v in self.config.confusable_map.items()}
        result = []
        for ch in text:
            result.append(str_map.get(ch, ch))
        return "".join(result)

    def _strip_evasion_separators(self, text: str) -> str:
        """Strip separator characters inserted between isolated CJK chars.

        Attackers insert separators like / | - between characters of a
        sensitive keyword to evade substring matching: 违/禁/词 → 违禁词.

        Only removes separators when BOTH adjacent CJK characters are
        "isolated" — meaning each is immediately next to another separator
        or a text boundary, NOT part of a multi-character CJK word.

        This preserves separators in normal usage:
            违/禁/词    → 违禁词      (evasion, removed ✓)
            你/好       → 你好        (evasion, removed ✓)
            是///消防员  → 是消防员    (chain with multi-char word ✓)
            双肩包/单肩包 → kept       (normal usage ✓)
            http://a/b  → kept        (non-CJK ✓)
            加微信/QQ    → kept        (one side non-CJK ✓)
        """
        chars = list(text)
        n = len(chars)
        # Positions marked for removal
        remove = [False] * n

        i = 0
        while i < n:
            if chars[i] in _EVASION_SEPARATORS:
                # Walk left past spaces and other separators to find a
                # significant character
                left = i - 1
                while left >= 0 and (chars[left].isspace() or chars[left] in _EVASION_SEPARATORS):
                    left -= 1

                # Walk right past spaces and other separators
                right = i + 1
                while right < n and (chars[right].isspace() or chars[right] in _EVASION_SEPARATORS):
                    right += 1

                # Both sides must exist and be CJK
                if left >= 0 and right < n:
                    if _is_cjk(chars[left]) and _is_cjk(chars[right]):
                        # Check isolation: a CJK char is "isolated" when it is
                        # NOT adjacent to another CJK char on its "outer" side.
                        # We require at least ONE side to be isolated — this
                        # catches chains like 是///消防员 (是 is isolated even
                        # though 消 is part of a multi-char word) while still
                        # preserving 双肩包/单肩包 (neither 包 nor 单 is isolated).
                        left_isolated = (left == 0 or
                                         not _is_cjk(chars[left - 1]))
                        right_isolated = (right == n - 1 or
                                          not _is_cjk(chars[right + 1]))

                        if left_isolated or right_isolated:
                            remove[i] = True
                            # Also remove spaces between the removed sep and
                            # the isolated CJK chars
                            _mark_adjacent_spaces(chars, i, n, remove)

            i += 1

        return "".join(ch for i, ch in enumerate(chars) if not remove[i])

    def _reduce_repeats(self, text: str) -> str:
        """Reduce consecutive repeated characters.

        E.g., with max_repeat=3, "aaaaaa" → "aaa"
        """
        max_r = self.config.max_repeat
        return re.sub(r"(.)\1{" + str(max_r) + r",}", r"\1" * max_r, text)

    def _normalize_symbols(self, text: str) -> str:
        """Normalize common variant symbols to standard forms.

        Handles: Chinese punctuation variants, common leetspeak,
        visually similar character substitutions.
        """
        symbol_map = {
            # Chinese punctuation → English
            "‘": "'", "’": "'",  # 左/右单引号
            "“": '"', "”": '"',  # 左/右双引号
            "，": ",",  # 全角逗号
            "。": ".",  # 句号
            "；": ";",  # 全角分号
            # Common leetspeak
            "@": "a",
            "$": "s",
            "0": "o",
        }
        result = []
        for ch in text:
            result.append(symbol_map.get(ch, ch))
        return "".join(result)


def _mark_adjacent_spaces(chars: list[str], idx: int, n: int,
                          remove: list[bool]) -> None:
    """Mark spaces immediately adjacent to a removed separator for cleanup.

    When we remove "/" from "违 / 禁", we also want to remove the spaces
    so we get "违禁" not "违  禁".  The whitespace normalizer (running
    after this step) would collapse remaining gaps anyway, but removing
    them here keeps the output clean.
    """
    # Left side spaces
    j = idx - 1
    while j >= 0 and chars[j].isspace() and not remove[j]:
        # Only remove if this space is between the removed sep and an isolated CJK
        remove[j] = True
        j -= 1
    # Right side spaces
    j = idx + 1
    while j < n and chars[j].isspace() and not remove[j]:
        remove[j] = True
        j += 1
