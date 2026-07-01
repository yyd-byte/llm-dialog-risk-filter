"""Text normalization — handles evasion techniques before detection."""

import re
from dataclasses import dataclass, field


@dataclass
class NormalizerConfig:
    """Configuration for TextNormalizer."""

    lowercase: bool = True
    full_to_half: bool = True
    normalize_whitespace: bool = True
    reduce_repeated_chars: bool = True
    max_repeat: int = 3
    normalize_symbols: bool = True


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
    normalization, repeated character compression, and symbol normalization.
    """

    def __init__(self, config: NormalizerConfig | None = None):
        self.config = config or NormalizerConfig()

    def normalize(self, text: str) -> NormalizedText:
        """Apply all enabled normalization steps."""
        result = text
        for step in [
            self._normalize_full_to_half,
            self._normalize_case,
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
            "_reduce_repeats": self.config.reduce_repeated_chars,
            "_normalize_symbols": self.config.normalize_symbols,
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