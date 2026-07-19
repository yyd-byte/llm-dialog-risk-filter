"""规则与规则类别数据模型。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.decision.models import RiskCategory, RiskLevel


@dataclass
class Rule:
    """单条检测规则（关键词或正则）。"""

    id: str                       # 规则唯一标识
    pattern: str                  # 关键词或正则表达式
    pattern_type: str = "keyword" # "keyword" | "regex"
    category: RiskCategory = RiskCategory.SENSITIVE
    risk_level: RiskLevel = RiskLevel.HIGH
    enabled: bool = True
    description: str = ""         # 规则检测目标说明
    source: str = ""              # 规则来源标识
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RuleMatch:
    """单次规则匹配结果。"""

    rule: Rule
    matched_text: str             # 实际命中的文本片段
    position: tuple[int, int] = (0, 0)  # 在规范化文本中的 (start, end)


@dataclass
class RuleCategoryMeta:
    """规则类别元数据。"""

    category: RiskCategory
    label: str             # 中文标签
    description: str       # 类别说明
    rule_count: int = 0
    enabled_count: int = 0