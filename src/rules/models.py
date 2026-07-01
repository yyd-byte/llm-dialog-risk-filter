"""Rule and rule-category data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.decision.models import RiskCategory, RiskLevel


@dataclass
class Rule:
    """A single detection rule (keyword or regex)."""

    id: str                          # Unique rule ID
    pattern: str                     # Keyword or regex pattern
    pattern_type: str = "keyword"    # "keyword" | "regex"
    category: RiskCategory = RiskCategory.SENSITIVE
    risk_level: RiskLevel = RiskLevel.HIGH
    enabled: bool = True
    description: str = ""            # What this rule detects
    source: str = ""                 # Where this rule came from
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RuleMatch:
    """Result of a single rule match during detection."""

    rule: Rule
    matched_text: str        # The actual text fragment that matched
    position: tuple[int, int] = (0, 0)  # (start, end) in normalized text


@dataclass
class RuleCategoryMeta:
    """Metadata for a rule category."""

    category: RiskCategory
    label: str             # 中文标签
    description: str       # 类别说明
    rule_count: int = 0
    enabled_count: int = 0