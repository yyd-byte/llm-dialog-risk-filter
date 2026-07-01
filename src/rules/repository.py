"""Rule file loading and saving (YAML backend)."""

import os
from pathlib import Path
from typing import Optional

import yaml

from src.rules.models import Rule, RuleMatch
from src.decision.models import RiskCategory, RiskLevel
from src.utils.exceptions import RuleLoadError


class RuleRepository:
    """Load and save rule files from YAML."""

    def __init__(self, rules_dir: str):
        self.rules_dir = Path(rules_dir)
        if not self.rules_dir.exists():
            raise RuleLoadError(f"Rules directory not found: {rules_dir}")

    def load_category(self, category: RiskCategory) -> list[Rule]:
        """Load all rules for a given category."""
        filename = f"{category.value}.yaml"
        filepath = self.rules_dir / filename
        if not filepath.exists():
            return []
        return self._parse_rule_file(filepath)

    def load_all(self) -> dict[RiskCategory, list[Rule]]:
        """Load all rules from all category files."""
        result: dict[RiskCategory, list[Rule]] = {}
        for cat in RiskCategory:
            result[cat] = self.load_category(cat)
        return result

    def save_category(self, category: RiskCategory, rules: list[Rule]) -> None:
        """Save rules for a category to YAML file."""
        filename = f"{category.value}.yaml"
        filepath = self.rules_dir / filename
        data = {
            "category": category.value,
            "label": self._category_label(category),
            "description": self._category_description(category),
            "rules": [self._rule_to_dict(r) for r in rules],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def _parse_rule_file(self, filepath: Path) -> list[Rule]:
        """Parse a single YAML rule file into Rule objects."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise RuleLoadError(f"Failed to parse {filepath}: {e}")

        if not data or "rules" not in data:
            return []

        rules = []
        for item in data["rules"]:
            rules.append(Rule(
                id=item.get("id", ""),
                pattern=item.get("pattern", ""),
                pattern_type=item.get("pattern_type", "keyword"),
                category=RiskCategory(data.get("category", data.get("category", "sensitive"))),
                risk_level=RiskLevel(item.get("risk_level", "high")),
                enabled=item.get("enabled", True),
                description=item.get("description", ""),
            ))
        return rules

    def _rule_to_dict(self, rule: Rule) -> dict:
        """Convert a Rule object to a dictionary for YAML serialization."""
        return {
            "id": rule.id,
            "pattern": rule.pattern,
            "pattern_type": rule.pattern_type,
            "risk_level": rule.risk_level.value,
            "enabled": rule.enabled,
            "description": rule.description,
        }

    @staticmethod
    def _category_label(category: RiskCategory) -> str:
        labels = {
            RiskCategory.SEXUAL: "色情低俗",
            RiskCategory.VIOLENT: "暴力危险",
            RiskCategory.ADVERTISING: "广告引流",
            RiskCategory.SENSITIVE: "敏感话术",
        }
        return labels.get(category, "")

    @staticmethod
    def _category_description(category: RiskCategory) -> str:
        descriptions = {
            RiskCategory.SEXUAL: "检测色情、低俗、性暗示等违规内容",
            RiskCategory.VIOLENT: "检测暴力、威胁、自残、危险行为等违规内容",
            RiskCategory.ADVERTISING: "检测广告推广、联系方式引流、重复营销话术等违规内容",
            RiskCategory.SENSITIVE: "检测政治敏感、违法违规、谣言等敏感话术",
        }
        return descriptions.get(category, "")