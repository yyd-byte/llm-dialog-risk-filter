"""Fragment-level desensitization — replaces sensitive fragments without deleting whole sentences."""

import re
from dataclasses import dataclass
from typing import Optional

from src.decision.models import Evidence, RiskCategory, RiskResult


@dataclass
class DesensitizeConfig:
    """Configuration for desensitization."""

    replacement_char: str = "*"
    keep_first_last: bool = True  # Preserve first and last character of replaced fragment


@dataclass
class DesensitizeResult:
    """Result of desensitization."""

    original: str
    desensitized: str
    replaced_fragments: list[dict]  # [{original, replacement, category, reason}]


class Desensitizer:
    """Replaces sensitive fragments with masked characters.

    Design principle: fragment-level replacement, not whole-sentence deletion.
    Preserves as much of the user's compliant intent as possible.
    """

    def __init__(self, config: DesensitizeConfig | None = None):
        self.config = config or DesensitizeConfig()

    def desensitize(self, text: str, risk_result: RiskResult) -> DesensitizeResult:
        """Apply desensitization to text based on risk result.

        Only replaces fragments that were matched by evidence, not the entire text.
        """
        if risk_result.is_safe:
            return DesensitizeResult(
                original=text,
                desensitized=text,
                replaced_fragments=[],
            )

        replaced = []
        result_text = text

        for evidence in risk_result.evidence_chain:
            if not evidence.matched_text:
                continue

            fragment = evidence.matched_text
            if fragment not in result_text:
                continue

            replacement = self._make_replacement(fragment)
            result_text = result_text.replace(fragment, replacement, 1)
            replaced.append({
                "original": fragment,
                "replacement": replacement,
                "category": evidence.category.value if evidence.category else "unknown",
                "reason": evidence.explanation,
            })

        return DesensitizeResult(
            original=text,
            desensitized=result_text,
            replaced_fragments=replaced,
        )

    def _make_replacement(self, text: str) -> str:
        """Create a replacement string for a fragment."""
        ch = self.config.replacement_char
        if self.config.keep_first_last and len(text) > 2:
            return text[0] + ch * (len(text) - 2) + text[-1]
        return ch * len(text)

    def category_label(self, category: RiskCategory) -> str:
        """Get human-readable label for a risk category."""
        labels = {
            RiskCategory.SEXUAL: "色情低俗内容",
            RiskCategory.VIOLENT: "暴力危险内容",
            RiskCategory.ADVERTISING: "广告引流内容",
            RiskCategory.SENSITIVE: "敏感内容",
        }
        return labels.get(category, "违规内容")