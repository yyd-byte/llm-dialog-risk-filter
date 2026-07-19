"""风险融合 — 将规则和语义检测结果合并为统一的风险决策。"""

from dataclasses import dataclass, field

from src.decision.models import Evidence, RiskCategory, RiskLevel, RiskResult


@dataclass
class FusionConfig:
    """风险融合配置。

    用于控制融合策略的阈值、权重和规则层置信度映射。
    """

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
        """校验阈值、权重和规则层置信度的合法性。

        Raises:
            ValueError: 当 rule_confidence 未覆盖所有风险等级、置信度不满足
                        0 <= low < medium < high <= 1、阈值不满足
                        0 <= medium < high <= 1、权重为负数、或两个权重同时为零时抛出。
        """
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
    """从 YAML 字典构建已验证的融合配置。

    Args:
        config: YAML 中 risk_fusion 段的配置字典。

    Returns:
        校验通过的 FusionConfig 实例。
    """
    default_confidence = FusionConfig().rule_confidence
    confidence = {
        **default_confidence,
        **{
            RiskLevel(level): float(score)
            for level, score in config.get("rule_confidence", {}).items()
        },
    }
    return FusionConfig(
        high_threshold=float(config.get("high_threshold", 0.8)),
        medium_threshold=float(config.get("medium_threshold", 0.4)),
        rule_weight=float(config.get("rule_weight", 0.5)),
        semantic_weight=float(config.get("semantic_weight", 0.5)),
        rule_confidence=confidence,
    )


class RiskFusion:
    """将规则和语义证据融合为可解释的风险决策。

    融合策略：
    1. 任一规则声明 HIGH → 直接定级 HIGH
    2. 同类别内，规则层 noisy-or 聚合 + 语义层取最大值，加权平均
    3. 跨类别取最高分，按阈值定级 HIGH/MEDIUM/LOW
    """

    def __init__(self, config: FusionConfig | None = None):
        self.config = config or FusionConfig()

    def evaluate(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """对规则和语义证据进行融合，输出统一的风险评估结果。

        Args:
            rule_evidence: 规则检测层产生的证据列表。
            semantic_evidence: 语义检测层产生的证据列表，可为 None。

        Returns:
            包含风险等级、类别、置信度和完整证据链的 RiskResult。
        """
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
        """评估输入侧的风险。"""
        return self.evaluate(rule_evidence, semantic_evidence)

    def evaluate_output(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """评估输出侧的风险。"""
        return self.evaluate(rule_evidence, semantic_evidence)

    def _category_score(
        self,
        category: RiskCategory,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence],
    ) -> float:
        """计算单个风险类别的融合置信度。

        同类别内：规则层 noisy-or 聚合，语义层取最大值，
        如果两者均有值则加权平均并与各层级分数取最大值。
        """
        category_rules = [evidence for evidence in rule_evidence if evidence.category == category]
        category_semantic = [
            evidence for evidence in semantic_evidence if evidence.category == category
        ]
        rule_score = self._noisy_or([evidence.confidence for evidence in category_rules])
        semantic_score = self._max_confidence(category_semantic)
        if rule_score and semantic_score:
            total_weight = self.config.rule_weight + self.config.semantic_weight
            weighted = (
                self.config.rule_weight * rule_score + self.config.semantic_weight * semantic_score
            ) / total_weight
            return max(weighted, rule_score, semantic_score)
        return rule_score or semantic_score

    @staticmethod
    def _deduplicate_rule_evidence(evidence_list: list[Evidence]) -> list[Evidence]:
        """按类别和归一化匹配文本保留每个规则信号的最强证据。"""
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
        """使用 noisy-or 聚合独立规则信号，结果不超过 1。"""
        score = 1.0
        for confidence in confidences:
            score *= 1 - confidence
        return 1 - score

    @staticmethod
    def _max_confidence(evidence_list: list[Evidence]) -> float:
        """返回证据列表中的最高置信度值。"""
        return max((evidence.confidence for evidence in evidence_list), default=0.0)

    def _best_category(
        self, category_scores: dict[RiskCategory, float]
    ) -> tuple[RiskCategory | None, float]:
        """选择置信度最高的风险类别，枚举顺序作为确定性平局裁决。"""
        category = max(RiskCategory, key=lambda item: category_scores[item])
        confidence = category_scores[category]
        return (category, confidence) if confidence else (None, 0.0)

    def _risk_level_for(self, confidence: float) -> RiskLevel:
        """将聚合置信度映射到配置的风险等级。

        高阈值以上为 HIGH，中阈值以上为 MEDIUM，否则为 LOW。
        """
        if confidence >= self.config.high_threshold:
            return RiskLevel.HIGH
        if confidence >= self.config.medium_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _first_category(categories: list[RiskCategory]) -> RiskCategory:
        """按稳定的枚举顺序返回第一个匹配类别。"""
        return next(category for category in RiskCategory if category in categories)

    @staticmethod
    def evidence_summary(result: RiskResult) -> str:
        """生成风险评估结果的可读摘要。"""
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
