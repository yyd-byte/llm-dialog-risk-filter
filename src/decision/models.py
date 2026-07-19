"""风险等级与决策相关数据模型。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    """三级风险分类。

    HIGH:   高风险 — 直接拦截
    MEDIUM: 中风险 — 脱敏后放行
    LOW:    低风险/正常 — 直接放行
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskCategory(str, Enum):
    """四类风险类别（按赛题规范定义）。

    SEXUAL:      色情低俗
    VIOLENT:     暴力危险
    ADVERTISING: 广告引流
    SENSITIVE:   敏感话术
    """

    SEXUAL = "sexual"
    VIOLENT = "violent"
    ADVERTISING = "advertising"
    SENSITIVE = "sensitive"


class DetectionSource(str, Enum):
    """检测结果来源。

    RULE:     规则引擎命中
    SEMANTIC: 语义模型判断
    """

    RULE = "rule"
    SEMANTIC = "semantic"


@dataclass
class Evidence:
    """单条风险证据。

    记录产生证据的流水线步骤、命中内容、置信度及可解释说明。
    """

    source: DetectionSource
    category: RiskCategory
    confidence: float  # 0.0 ~ 1.0
    matched_pattern: str = ""  # 命中的关键词/正则
    matched_text: str = ""  # 命中的原文片段
    explanation: str = ""  # 可解释的说明
    step: str = ""  # 产生证据的流水线步骤: "normalize" | "rule" | "semantic" | "fusion" | "desensitize"
    declared_risk_level: RiskLevel | None = None  # 规则配置声明的风险等级；语义证据保持为空
    metadata: dict = field(default_factory=dict)  # 附加结构化数据，用于前端可视化


@dataclass
class RiskResult:
    """单侧（输入或输出）的统一风险评估结果。"""

    risk_level: RiskLevel
    risk_category: Optional[RiskCategory] = None
    confidence: float = 0.0  # 0.0 ~ 1.0
    evidence_chain: list[Evidence] = field(default_factory=list)
    is_safe: bool = True  # LOW 时为 True，否则为 False

    def __post_init__(self):
        self.is_safe = self.risk_level == RiskLevel.LOW

    @property
    def action(self) -> str:
        """根据风险等级返回对应的处置动作。"""
        actions = {
            RiskLevel.HIGH: "block",
            RiskLevel.MEDIUM: "desensitize",
            RiskLevel.LOW: "pass",
        }
        return actions[self.risk_level]
