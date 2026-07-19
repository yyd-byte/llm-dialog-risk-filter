"""片段级脱敏 — 替换敏感片段，保留句子结构和语义，避免整句删除。

支持三种脱敏模式：
- "mask":     用 *** 替换（保留首尾字符）
- "semantic": 用类别标签替换，如微信号 → [联系方式]，保留语义意图供 LLM 理解
- "rewrite":  语义标签替换 + LLM 自然化重写，将标签化的文本改写为自然安全的中文表达
              无 LLM 时自动回退到 semantic 模式。
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
    """脱敏配置 — 控制脱敏模式、替换字符、语义标签和 LLM 改写参数。"""

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
    """脱敏结果 — 原始文本、脱敏后文本、替换片段列表及改写标记。"""

    original: str
    desensitized: str
    replaced_fragments: list[dict]  # [{original, replacement, category, reason}]
    was_rewritten: bool = False    # True if LLM rewrite was applied


class Desensitizer:
    """替换敏感片段，保留句子结构。

    三种工作模式：
    mask      — *** 替换（旧版兼容）
    semantic  — 类别标签替换：微信号 → [联系方式]
    rewrite   — 标签 + LLM 自然化：[联系方式] → 私下联系

    rewrite 模式下通过 llm_call 参数传入 LLM 调用函数，无 LLM 时自动回退。
    """

    def __init__(self, config: DesensitizeConfig | None = None):
        self.config = config or DesensitizeConfig()

    def desensitize(self, text: str, risk_result: RiskResult,
                    llm_call: Callable[[str], str] | None = None,
                    ) -> DesensitizeResult:
        """根据风险检测结果对文本执行脱敏处理。

        Args:
            text: 原始用户输入文本。
            risk_result: 包含证据链的风险评估结果。
            llm_call: 可选的 LLM 调用函数（用于 rewrite 模式），
                      接收提示文本，返回 LLM 响应。

        仅替换被证据命中的片段，未命中的内容保持不变。
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
        """为敏感片段生成替换字符串。

        在 "mask" 模式下：微信号 → 微**号
        在 "semantic" / "rewrite" 模式下：微信号 → [联系方式]
        """
        if self.config.mode in ("semantic", "rewrite"):
            return self._semantic_label(evidence)

        # Mask mode (legacy)
        ch = self.config.replacement_char
        if self.config.keep_first_last and len(text) > 2:
            return text[0] + ch * (len(text) - 2) + text[-1]
        return ch * len(text)

    def _semantic_label(self, evidence: Evidence | None) -> str:
        """根据证据的风险类别返回对应的语义替换标签。

        Args:
            evidence: 命中的证据对象。

        Returns:
            类别对应的语义标签字符串，如 [联系方式]、[不雅用语] 等。
        """
        if evidence is not None and evidence.category is not None:
            cat_key = evidence.category.value
            if cat_key in self.config.category_labels:
                return self.config.category_labels[cat_key]
        return self.config.fallback_label

    def category_label(self, category: RiskCategory) -> str:
        """获取风险类别的可读中文标签。

        Args:
            category: 风险类别枚举值。

        Returns:
            对应的中文标签，如"色情低俗内容"。
        """
        labels = {
            RiskCategory.SEXUAL: "色情低俗内容",
            RiskCategory.VIOLENT: "暴力危险内容",
            RiskCategory.ADVERTISING: "广告引流内容",
            RiskCategory.SENSITIVE: "敏感内容",
        }
        return labels.get(category, "违规内容")
