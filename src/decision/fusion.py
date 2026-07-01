"""Risk fusion — combines rule and semantic results into a unified risk decision."""

from dataclasses import dataclass
from typing import Optional

from src.decision.models import (
    Evidence,
    RiskCategory,
    RiskLevel,
    RiskResult,
    DetectionSource,
)


@dataclass
class FusionConfig:
    """Configuration for risk fusion."""

    high_threshold: float = 0.8
    medium_threshold: float = 0.4
    rule_weight: float = 0.5
    semantic_weight: float = 0.5


class RiskFusion:
    """Fuses rule-based and semantic detection results into a unified risk level.

    Produces an explainable evidence chain showing why each decision was made.
    """

    def __init__(self, config: FusionConfig | None = None):
        self.config = config or FusionConfig()

    def evaluate(self,
                 rule_evidence: list[Evidence],
                 semantic_evidence: list[Evidence] | None = None) -> RiskResult:
        """Combine rule and semantic evidence into a single risk result.

        Args:
            rule_evidence: Evidence from rule-based detection.
            semantic_evidence: Evidence from semantic model detection.

        Returns:
            RiskResult with unified risk level and full evidence chain.
        """
        semantic_evidence = semantic_evidence or []
        all_evidence = rule_evidence + semantic_evidence

        if not all_evidence:
            return RiskResult(
                risk_level=RiskLevel.LOW,
                confidence=0.0,
                evidence_chain=[],
            )

        # Calculate weighted confidence
        rule_conf = self._max_confidence(rule_evidence)
        sem_conf = self._max_confidence(semantic_evidence)

        weighted_conf = (
            self.config.rule_weight * rule_conf
            + self.config.semantic_weight * sem_conf
        )

        # Determine risk level
        if weighted_conf >= self.config.high_threshold:
            risk_level = RiskLevel.HIGH
        elif weighted_conf >= self.config.medium_threshold:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Determine primary category (highest confidence)
        primary_category = self._primary_category(all_evidence)

        return RiskResult(
            risk_level=risk_level,
            risk_category=primary_category,
            confidence=weighted_conf,
            evidence_chain=all_evidence,
        )

    def evaluate_input(self,
                       rule_evidence: list[Evidence],
                       semantic_evidence: list[Evidence] | None = None) -> RiskResult:
        """Evaluate risk for input side.

        Same as evaluate() but can apply different thresholds in the future.
        """
        return self.evaluate(rule_evidence, semantic_evidence)

    def evaluate_output(self,
                        rule_evidence: list[Evidence],
                        semantic_evidence: list[Evidence] | None = None) -> RiskResult:
        """Evaluate risk for output side.

        Output side may use stricter thresholds (TBD).
        """
        return self.evaluate(rule_evidence, semantic_evidence)

    # ---- Helpers ----

    @staticmethod
    def _max_confidence(evidence_list: list[Evidence]) -> float:
        """Get the highest confidence from a list of evidence."""
        if not evidence_list:
            return 0.0
        return max(e.confidence for e in evidence_list)

    @staticmethod
    def _primary_category(evidence_list: list[Evidence]) -> Optional[RiskCategory]:
        """Get the category with the highest confidence evidence."""
        if not evidence_list:
            return None
        return max(evidence_list, key=lambda e: e.confidence).category

    @staticmethod
    def evidence_summary(result: RiskResult) -> str:
        """Generate a human-readable summary of a risk result."""
        if result.is_safe:
            return "内容正常，放行"

        parts = [f"风险等级: {result.risk_level.value.upper()}"]
        if result.risk_category:
            parts.append(f"风险类别: {result.risk_category.value}")
        parts.append(f"置信度: {result.confidence:.2f}")

        if result.evidence_chain:
            parts.append("命中证据:")
            for ev in result.evidence_chain:
                parts.append(f"  - [{ev.source.value}] {ev.explanation}")

        return "\n".join(parts)