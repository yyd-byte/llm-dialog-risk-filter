"""Fragment-level desensitization — replaces sensitive fragments without deleting whole sentences.

Supports three modes:
- "mask": replaces with *** (legacy, preserves first/last char)
- "semantic": replaces with category-aware labels like [联系方式], [不雅用语]
  so the LLM can still understand user intent and respond appropriately.
- "rewrite": semantic label replacement + LLM naturalization — the LLM
  rewrites the labeled text into natural, safe Chinese that preserves the
  user's communication intent.  Falls back to semantic if no LLM available.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from src.decision.models import Evidence, RiskCategory, RiskResult


# ---- Default category → semantic replacement label ----

DEFAULT_SEMANTIC_LABELS: dict[str, str] = {
    "sexual": "[不雅用语]",
    "violent": "[暴力用语]",
    "advertising": "[联系方式]",
    "sensitive": "[敏感信息]",
}

# ---- Default prompt for LLM naturalization ----

DEFAULT_REWRITE_PROMPT = """改写以下文本。方括号（如 [联系方式]）标记了需要替换的敏感词。
将每个方括号替换为一个简短的中性词，不要删除，不要改变其他内容。

示例：
- "加我[联系方式]" → "加我联系方式"
- "[不雅用语]吧" → "来聊聊吧"

严格规则：
1. 每个方括号必须被替换为一个中性词语，不能直接删除
2. 替换后的句子应与原句意思一致
3. 不要添加建议、提醒或额外信息
4. 只输出改写后的一句话

文本：{text}
改写："""


@dataclass
class DesensitizeConfig:
    """Configuration for desensitization."""

    # Mode: "mask" | "semantic" | "rewrite"
    mode: str = "semantic"
    # For mask mode
    replacement_char: str = "*"
    keep_first_last: bool = True
    # For semantic mode
    category_labels: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SEMANTIC_LABELS))
    fallback_label: str = "[违规内容]"
    # For rewrite mode
    rewrite_prompt: str = DEFAULT_REWRITE_PROMPT


@dataclass
class DesensitizeResult:
    """Result of desensitization."""

    original: str
    desensitized: str
    replaced_fragments: list[dict]  # [{original, replacement, category, reason}]
    was_rewritten: bool = False    # True if LLM rewrite was applied


class Desensitizer:
    """Replaces sensitive fragments while preserving sentence structure.

    Three modes of operation:

    mask      — *** replacement (legacy)
    semantic  — category label replacement: 微信号 → [联系方式]
    rewrite   — semantic + LLM naturalization: [联系方式] → 私下联系

    In rewrite mode, pass an llm_call function to desensitize() that
    takes a prompt string and returns the LLM's text response.
    Falls back to semantic mode if llm_call is None.
    """

    def __init__(self, config: DesensitizeConfig | None = None):
        self.config = config or DesensitizeConfig()

    def desensitize(self, text: str, risk_result: RiskResult,
                    llm_call: Callable[[str], str] | None = None,
                    ) -> DesensitizeResult:
        """Apply desensitization to text based on risk result.

        Args:
            text: Original user input.
            risk_result: Risk assessment with evidence chain.
            llm_call: Optional LLM function for rewrite mode.
                      Takes a prompt string, returns the LLM response.

        Only replaces fragments that were matched by evidence.
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

            replacement = self._make_replacement(fragment, evidence)
            result_text = result_text.replace(fragment, replacement, 1)
            replaced.append({
                "original": fragment,
                "replacement": replacement,
                "category": evidence.category.value if evidence.category else "unknown",
                "reason": evidence.explanation,
            })

        # In rewrite mode, naturalize the labeled text via LLM
        was_rewritten = False
        if self.config.mode == "rewrite" and llm_call is not None:
            try:
                prompt = self.config.rewrite_prompt.format(text=result_text)
                rewritten = llm_call(prompt)
                if rewritten and len(rewritten.strip()) > 0:
                    result_text = rewritten.strip()
                    was_rewritten = True
            except Exception:
                # LLM call failed — keep semantic labels as fallback
                pass

        return DesensitizeResult(
            original=text,
            desensitized=result_text,
            replaced_fragments=replaced,
            was_rewritten=was_rewritten,
        )

    def _make_replacement(self, text: str,
                          evidence: Evidence | None = None) -> str:
        """Create a replacement string for a fragment.

        In "mask" mode: 微信号 → 微**号
        In "semantic" / "rewrite" mode: 微信号 → [联系方式]
        """
        if self.config.mode in ("semantic", "rewrite"):
            return self._semantic_label(evidence)

        # Mask mode (legacy)
        ch = self.config.replacement_char
        if self.config.keep_first_last and len(text) > 2:
            return text[0] + ch * (len(text) - 2) + text[-1]
        return ch * len(text)

    def _semantic_label(self, evidence: Evidence | None) -> str:
        """Get the semantic replacement label for an evidence's category."""
        if evidence is not None and evidence.category is not None:
            cat_key = evidence.category.value
            if cat_key in self.config.category_labels:
                return self.config.category_labels[cat_key]
        return self.config.fallback_label

    def category_label(self, category: RiskCategory) -> str:
        """Get human-readable label for a risk category."""
        labels = {
            RiskCategory.SEXUAL: "色情低俗内容",
            RiskCategory.VIOLENT: "暴力危险内容",
            RiskCategory.ADVERTISING: "广告引流内容",
            RiskCategory.SENSITIVE: "敏感内容",
        }
        return labels.get(category, "违规内容")
