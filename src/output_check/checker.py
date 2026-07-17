"""Output re-check — secondary content verification for LLM-generated responses."""

from dataclasses import dataclass
from typing import Optional

from src.decision.models import RiskResult, RiskLevel
from src.decision.fusion import RiskFusion
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.desensitization.desensitizer import Desensitizer


@dataclass
class OutputCheckResult:
    """Result of output-side content verification."""

    original_output: str
    is_safe: bool
    risk_result: Optional[RiskResult] = None
    safe_output: str = ""  # Replacement text if unsafe

    @property
    def final_output(self) -> str:
        """Return the safe replacement when output processing produced one."""
        return self.safe_output or self.original_output


class OutputChecker:
    """Re-checks LLM-generated content for safety before returning to user.

    This is the "safety net" layer — even if input was clean, the model
    might generate inappropriate content.

    Risk-level handling:
    - HIGH:   Block entirely, return block_message.
    - MEDIUM: Desensitize fragments, return cleaned output.
    - LOW:    Pass through unchanged.
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
        """Run output-side content verification.

        Args:
            llm_output: The raw output from the LLM.

        Returns:
            OutputCheckResult with safety verdict and (if needed) safe replacement.
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
