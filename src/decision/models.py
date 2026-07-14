"""Risk level and decision-related data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    """Three-tier risk classification."""

    HIGH = "high"       # 高风险 — 直接拦截
    MEDIUM = "medium"   # 中风险 — 脱敏后放行
    LOW = "low"         # 低风险/正常 — 直接放行


class RiskCategory(str, Enum):
    """Four risk categories as defined in the spec."""

    SEXUAL = "sexual"           # 色情低俗
    VIOLENT = "violent"         # 暴力危险
    ADVERTISING = "advertising" # 广告引流
    SENSITIVE = "sensitive"     # 敏感话术


class DetectionSource(str, Enum):
    """Source of a detection result."""

    RULE = "rule"       # 规则引擎命中
    SEMANTIC = "semantic"  # 语义模型判断


@dataclass
class Evidence:
    """A single piece of evidence for a risk decision.

    Tracks which pipeline step produced the evidence, along with
    the matched content, confidence, and human-readable explanation.
    """

    source: DetectionSource
    category: RiskCategory
    confidence: float  # 0.0 ~ 1.0
    matched_pattern: str = ""     # 命中的关键词/正则
    matched_text: str = ""        # 命中的原文片段
    explanation: str = ""         # 可解释的说明
    # Pipeline step that generated this evidence:
    # "normalize" | "rule" | "semantic" | "fusion" | "desensitize"
    step: str = ""
    # Extra structured data for rich visualization
    metadata: dict = field(default_factory=dict)


@dataclass
class RiskResult:
    """Unified risk assessment result for one side (input or output)."""

    risk_level: RiskLevel
    risk_category: Optional[RiskCategory] = None
    confidence: float = 0.0  # 0.0 ~ 1.0
    evidence_chain: list[Evidence] = field(default_factory=list)
    is_safe: bool = True  # True if LOW risk, False otherwise

    def __post_init__(self):
        self.is_safe = self.risk_level == RiskLevel.LOW

    @property
    def action(self) -> str:
        """Human-readable action based on risk level."""
        actions = {
            RiskLevel.HIGH: "block",
            RiskLevel.MEDIUM: "desensitize",
            RiskLevel.LOW: "pass",
        }
        return actions[self.risk_level]