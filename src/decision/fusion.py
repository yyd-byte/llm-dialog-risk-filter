"""Risk fusion — combines rule and semantic results into a unified risk decision."""

from dataclasses import dataclass, field

from src.decision.models import Evidence, RiskCategory, RiskLevel, RiskResult


@dataclass
class FusionConfig:
    """Configuration for risk fusion."""

    high_threshold: float = 0.8
    medium_threshold: float = 0.4
    rule_weight: float = 0.5
    semantic_weight: float = 0.5
    rule_confidence: dict[RiskLevel, float] = field(
        default_factory=lambda: {
            RiskLevel.LOW: 0.2,
            RiskLevel.MEDIUM: 0.58,
            RiskLevel.HIGH: 1.0,
        }
    )

    def __post_init__(self) -> None:
        """Validate thresholds, weights, and rule-level confidence values."""
        required_levels = set(RiskLevel)
        if set(self.rule_confidence) != required_levels:
            raise ValueError("rule_confidence must define low, medium, and high")
        low = self.rule_confidence[RiskLevel.LOW]
        medium = self.rule_confidence[RiskLevel.MEDIUM]
        high = self.rule_confidence[RiskLevel.HIGH]
        if not 0 <= low < medium < high <= 1:
            raise ValueError("rule confidence must satisfy 0 <= low < medium < high <= 1")
        if not 0 <= self.medium_threshold < self.high_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 <= medium < high <= 1")
        if self.rule_weight < 0 or self.semantic_weight < 0:
            raise ValueError("source weights cannot be negative")
        if self.rule_weight == 0 and self.semantic_weight == 0:
            raise ValueError("at least one source weight must be positive")


def fusion_config_from_dict(config: dict) -> FusionConfig:
    """Build validated fusion configuration from a YAML-compatible mapping."""
    confidence = {
        RiskLevel(level): float(score) for level, score in config.get("rule_confidence", {}).items()
    }
    return FusionConfig(
        high_threshold=float(config.get("high_threshold", 0.8)),
        medium_threshold=float(config.get("medium_threshold", 0.4)),
        rule_weight=float(config.get("rule_weight", 0.5)),
        semantic_weight=float(config.get("semantic_weight", 0.5)),
        rule_confidence=confidence or FusionConfig().rule_confidence,
    )


class RiskFusion:
    """Fuse rule and semantic evidence into an explainable risk decision."""

    def __init__(self, config: FusionConfig | None = None):
        self.config = config or FusionConfig()

    def evaluate(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """Combine rule and semantic evidence into a single risk result."""
        semantic_evidence = semantic_evidence or []
        all_evidence = rule_evidence + semantic_evidence
        if not all_evidence:
            return RiskResult(risk_level=RiskLevel.LOW, confidence=0.0)

        deduplicated_rules = self._deduplicate_rule_evidence(rule_evidence)
        high_categories = [
            evidence.category
            for evidence in deduplicated_rules
            if evidence.declared_risk_level == RiskLevel.HIGH
        ]
        if high_categories:
            category = self._first_category(high_categories)
            return RiskResult(
                risk_level=RiskLevel.HIGH,
                risk_category=category,
                confidence=self.config.rule_confidence[RiskLevel.HIGH],
                evidence_chain=all_evidence,
            )

        category_scores = {
            category: self._category_score(category, deduplicated_rules, semantic_evidence)
            for category in RiskCategory
        }
        category, confidence = self._best_category(category_scores)
        risk_level = self._risk_level_for(confidence)
        return RiskResult(
            risk_level=risk_level,
            risk_category=category,
            confidence=confidence,
            evidence_chain=all_evidence,
        )

    def evaluate_input(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """Evaluate risk for input side."""
        return self.evaluate(rule_evidence, semantic_evidence)

    def evaluate_output(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """Evaluate risk for output side."""
        return self.evaluate(rule_evidence, semantic_evidence)

    def _category_score(
        self,
        category: RiskCategory,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence],
    ) -> float:
        category_rules = [evidence for evidence in rule_evidence if evidence.category == category]
        category_semantic = [
            evidence for evidence in semantic_evidence if evidence.category == category
        ]
        rule_score = self._noisy_or([evidence.confidence for evidence in category_rules])
        semantic_score = self._max_confidence(category_semantic)
        if rule_score and semantic_score:
            total_weight = self.config.rule_weight + self.config.semantic_weight
            return (
                self.config.rule_weight * rule_score + self.config.semantic_weight * semantic_score
            ) / total_weight
        return rule_score or semantic_score

    @staticmethod
    def _deduplicate_rule_evidence(evidence_list: list[Evidence]) -> list[Evidence]:
        """Retain the strongest rule signal per category and normalized match."""
        unique: dict[tuple[RiskCategory, str], Evidence] = {}
        for evidence in evidence_list:
            match_key = " ".join(evidence.matched_text.casefold().split())
            key = (evidence.category, match_key)
            existing = unique.get(key)
            if existing is None or evidence.confidence > existing.confidence:
                unique[key] = evidence
        return list(unique.values())

    @staticmethod
    def _noisy_or(confidences: list[float]) -> float:
        """Aggregate independent rule signals without exceeding one."""
        score = 1.0
        for confidence in confidences:
            score *= 1 - confidence
        return 1 - score

    @staticmethod
    def _max_confidence(evidence_list: list[Evidence]) -> float:
        """Return the highest confidence from an evidence list."""
        return max((evidence.confidence for evidence in evidence_list), default=0.0)

    def _best_category(
        self, category_scores: dict[RiskCategory, float]
    ) -> tuple[RiskCategory | None, float]:
        """Select the strongest category using enum order as a deterministic tie-breaker."""
        category = max(RiskCategory, key=lambda item: category_scores[item])
        confidence = category_scores[category]
        return (category, confidence) if confidence else (None, 0.0)

    def _risk_level_for(self, confidence: float) -> RiskLevel:
        """Map an aggregate confidence to the configured risk tier."""
        if confidence >= self.config.high_threshold:
            return RiskLevel.HIGH
        if confidence >= self.config.medium_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _first_category(categories: list[RiskCategory]) -> RiskCategory:
        """Return the first category in stable enum order."""
        return next(category for category in RiskCategory if category in categories)

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
            for evidence in result.evidence_chain:
                parts.append(f"  - [{evidence.source.value}] {evidence.explanation}")
        return "\n".join(parts)
