"""输出复检 — 对 LLM 生成的回复进行二次内容安全校验。"""

from dataclasses import dataclass
from typing import Optional

from src.decision.models import RiskResult, RiskLevel
from src.decision.fusion import RiskFusion
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.desensitization.desensitizer import Desensitizer


@dataclass
class OutputCheckResult:
    """输出复检结果 — 安全判定、风险详情和替换文本。"""

    original_output: str
    is_safe: bool
    risk_result: Optional[RiskResult] = None
    safe_output: str = ""  # Replacement text if unsafe

    @property
    def final_output(self) -> str:
        """返回可安全展示的内容，被拦截时绝不返回原始输出。"""
        if self.safe_output:
            return self.safe_output
        if self.is_safe:
            return self.original_output
        return "[内容已拦截]"


class OutputChecker:
    """对 LLM 输出进行二次安全校验，作为整个过滤链路的"安全网"。

    即使输入侧通过了检测，模型仍可能生成违规内容。
    本模块在输出返回用户之前再次扫描，按风险等级分三级处置：

    - HIGH:   完全拦截，返回合规提示话术
    - MEDIUM: 片段脱敏后放行
    - LOW:    直接放行
    """

    DEFAULT_BLOCK_MESSAGE = "抱歉，系统在处理您的请求时生成了不适宜内容，已被安全拦截。"

    def __init__(
        self,
        rule_detector: RuleDetector,
        semantic_detector: SemanticDetector,
        risk_fusion: RiskFusion,
        block_message: str | None = None,
        desensitizer: Desensitizer | None = None,
    ):
        self._rule_detector = rule_detector
        self._semantic_detector = semantic_detector
        self._risk_fusion = risk_fusion
        self.block_message = block_message or self.DEFAULT_BLOCK_MESSAGE
        self._desensitizer = desensitizer

    def check(self, llm_output: str) -> OutputCheckResult:
        """执行输出侧内容安全校验。

        Args:
            llm_output: LLM 生成的原始输出文本。

        Returns:
            包含安全判定结果和（如有必要）安全替换文本的 OutputCheckResult。
        """
        rule_evidence = self._rule_detector.detect(llm_output)
        semantic_evidence = self._semantic_detector.detect(llm_output)

        risk_result = self._risk_fusion.evaluate_output(rule_evidence, semantic_evidence)

        # Low risk — pass through
        if risk_result.is_safe:
            return OutputCheckResult(
                original_output=llm_output,
                is_safe=True,
                risk_result=risk_result,
                safe_output=llm_output,
            )

        # High risk — block entirely
        if risk_result.risk_level == RiskLevel.HIGH:
            return OutputCheckResult(
                original_output=llm_output,
                is_safe=False,
                risk_result=risk_result,
                safe_output=self.block_message,
            )

        # Medium risk — try desensitization instead of blocking
        if self._desensitizer:
            des_result = self._desensitizer.desensitize(llm_output, risk_result)
            if des_result.desensitized != llm_output:
                return OutputCheckResult(
                    original_output=llm_output,
                    is_safe=True,
                    risk_result=risk_result,
                    safe_output=des_result.desensitized,
                )

        # Fallback: no desensitizer or desensitization had no effect
        return OutputCheckResult(
            original_output=llm_output,
            is_safe=False,
            risk_result=risk_result,
            safe_output=self.block_message,
        )
