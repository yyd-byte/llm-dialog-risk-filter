"""Rule management — CRUD operations, enable/disable, import/export."""

import copy
from datetime import datetime
from typing import Optional

from src.rules.models import Rule, RuleCategoryMeta, RuleMatch
from src.rules.repository import RuleRepository
from src.decision.models import RiskCategory, RiskLevel


class RuleManager:
    """Manages the lifecycle of detection rules.

    Provides CRUD, enable/disable toggle, batch import/export, and
    category-level statistics.
    """

    def __init__(self, repository: RuleRepository):
        self._repo = repository
        self._rules: dict[RiskCategory, list[Rule]] = {}
        self.reload()

    # ---- Lifecycle ----

    def reload(self) -> None:
        """Reload all rules from disk."""
        self._rules = self._repo.load_all()

    def save(self) -> None:
        """Save all rules to disk."""
        for category, rules in self._rules.items():
            self._repo.save_category(category, rules)

    # ---- Query ----

    def get_enabled_rules(self, category: Optional[RiskCategory] = None) -> list[Rule]:
        """Get all enabled rules, optionally filtered by category."""
        if category:
            return [r for r in self._rules.get(category, []) if r.enabled]
        result = []
        for rules in self._rules.values():
            result.extend(r for r in rules if r.enabled)
        return result

    def get_all_rules(self, category: Optional[RiskCategory] = None) -> list[Rule]:
        """Get all rules, optionally filtered by category."""
        if category:
            return list(self._rules.get(category, []))
        result = []
        for rules in self._rules.values():
            result.extend(rules)
        return result

    def get_rule_by_id(self, rule_id: str) -> Optional[Rule]:
        """Find a rule by its unique ID."""
        for rules in self._rules.values():
            for r in rules:
                if r.id == rule_id:
                    return r
        return None

    # ---- Mutation ----

    def add_rule(self, rule: Rule) -> None:
        """Add a new rule to its category."""
        self._rules.setdefault(rule.category, []).append(rule)

    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """Update fields of an existing rule. Returns True if found."""
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            return False
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        rule.updated_at = datetime.now().isoformat()
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by ID. Returns True if found and deleted."""
        for cat, rules in self._rules.items():
            for i, r in enumerate(rules):
                if r.id == rule_id:
                    self._rules[cat].pop(i)
                    return True
        return False

    def toggle_rule(self, rule_id: str) -> bool:
        """Toggle a rule's enabled status. Returns True if found."""
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            return False
        rule.enabled = not rule.enabled
        rule.updated_at = datetime.now().isoformat()
        return True

    # ---- Statistics ----

    def get_category_meta(self) -> list[RuleCategoryMeta]:
        """Get metadata for all categories."""
        metas = []
        labels = {
            RiskCategory.SEXUAL: "色情低俗",
            RiskCategory.VIOLENT: "暴力危险",
            RiskCategory.ADVERTISING: "广告引流",
            RiskCategory.SENSITIVE: "敏感话术",
        }
        descriptions = {
            RiskCategory.SEXUAL: "检测色情、低俗、性暗示等违规内容",
            RiskCategory.VIOLENT: "检测暴力、威胁、自残、危险行为等违规内容",
            RiskCategory.ADVERTISING: "检测广告推广、联系方式引流、重复营销话术等违规内容",
            RiskCategory.SENSITIVE: "检测政治敏感、违法违规、谣言等敏感话术",
        }
        for cat in RiskCategory:
            rules = self._rules.get(cat, [])
            metas.append(RuleCategoryMeta(
                category=cat,
                label=labels.get(cat, ""),
                description=descriptions.get(cat, ""),
                rule_count=len(rules),
                enabled_count=sum(1 for r in rules if r.enabled),
            ))
        return metas

    # ---- Import / Export ----

    def export_rules(self, category: RiskCategory) -> list[dict]:
        """Export rules as list of dicts."""
        return [
            {
                "id": r.id,
                "pattern": r.pattern,
                "pattern_type": r.pattern_type,
                "category": r.category.value,
                "risk_level": r.risk_level.value,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in self._rules.get(category, [])
        ]

    def import_rules(self, category: RiskCategory, rules_data: list[dict]) -> int:
        """Import rules from list of dicts. Returns count of imported rules."""
        count = 0
        for item in rules_data:
            rule = Rule(
                id=item.get("id", f"import-{datetime.now().timestamp()}"),
                pattern=item["pattern"],
                pattern_type=item.get("pattern_type", "keyword"),
                category=category,
                risk_level=RiskLevel(item.get("risk_level", "high")),
                enabled=item.get("enabled", True),
                description=item.get("description", ""),
            )
            self.add_rule(rule)
            count += 1
        return count