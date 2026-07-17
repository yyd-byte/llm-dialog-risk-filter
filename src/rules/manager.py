"""Rule management — queries, persistence, and enable-state operations."""

from datetime import datetime
from threading import RLock

from src.decision.models import RiskCategory, RiskLevel
from src.rules.models import Rule, RuleCategoryMeta
from src.rules.repository import RuleRepository


class RuleVersionConflictError(Exception):
    """Raised when a rule mutation targets an outdated ruleset version."""


class RuleManager:
    """Manage one in-memory rule snapshot backed by category YAML files."""

    def __init__(self, repository: RuleRepository):
        self._repo = repository
        self._lock = RLock()
        self._rules: dict[RiskCategory, list[Rule]] = {}
        self.reload()

    def reload(self) -> None:
        """Replace the current snapshot only after all files load successfully."""
        candidate = self._repo.load_all()
        with self._lock:
            self._rules = candidate

    def rebuild_version(self) -> str:
        """Return the current persisted ruleset version."""
        return self._repo.version()

    def get_enabled_rules(self, category: RiskCategory | None = None) -> list[Rule]:
        """Get enabled rules, optionally scoped to one category."""
        with self._lock:
            if category:
                return [rule for rule in self._rules.get(category, []) if rule.enabled]
            return [rule for rules in self._rules.values() for rule in rules if rule.enabled]

    def get_all_rules(self, category: RiskCategory | None = None) -> list[Rule]:
        """Get all rules, optionally scoped to one category."""
        with self._lock:
            if category:
                return list(self._rules.get(category, []))
            return [rule for rules in self._rules.values() for rule in rules]

    def add_rule(self, rule: Rule) -> None:
        """Add one rule to the current in-memory snapshot."""
        with self._lock:
            self._rules.setdefault(rule.category, []).append(rule)

    def get_rule_by_id(self, rule_id: str) -> Rule | None:
        """Find one rule by ID."""
        with self._lock:
            for rules in self._rules.values():
                for rule in rules:
                    if rule.id == rule_id:
                        return rule
        return None

    def list_rules(
        self,
        category: RiskCategory | None = None,
        source: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Rule], int]:
        """Return a stable filtered page of rules and its total count."""
        rules = self.get_all_rules(category)
        if source is not None:
            rules = [rule for rule in rules if rule.source == source]
        if enabled is not None:
            rules = [rule for rule in rules if rule.enabled == enabled]
        total = len(rules)
        start = (page - 1) * page_size
        return rules[start : start + page_size], total

    def set_rule_enabled(
        self,
        rule_id: str,
        enabled: bool,
        expected_version: str,
    ) -> tuple[Rule, str, bool]:
        """Persist an explicit enabled state and return rule, version, and prior state."""
        with self._lock:
            current_version = self._repo.version()
            if expected_version != current_version:
                raise RuleVersionConflictError(current_version)
            rule = self.get_rule_by_id(rule_id)
            if rule is None:
                raise KeyError(rule_id)
            previous_enabled = rule.enabled
            if previous_enabled != enabled:
                rule.enabled = enabled
                rule.updated_at = datetime.now().isoformat()
                self._repo.save_category(rule.category, self._rules[rule.category])
            return rule, self._repo.version(), previous_enabled

    def get_category_meta(self) -> list[RuleCategoryMeta]:
        """Get rule counts and labels for every category."""
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
        with self._lock:
            return [
                RuleCategoryMeta(
                    category=category,
                    label=labels[category],
                    description=descriptions[category],
                    rule_count=len(self._rules.get(category, [])),
                    enabled_count=sum(rule.enabled for rule in self._rules.get(category, [])),
                )
                for category in RiskCategory
            ]

    def source_counts(self) -> list[dict]:
        """Return deterministic provenance counts for loaded rules."""
        counts: dict[str, list[Rule]] = {}
        for rule in self.get_all_rules():
            counts.setdefault(rule.source, []).append(rule)
        return [
            {
                "source": source,
                "rule_count": len(rules),
                "enabled_count": sum(rule.enabled for rule in rules),
            }
            for source, rules in sorted(counts.items())
        ]

    def export_rules(self, category: RiskCategory) -> list[dict]:
        """Export rules as serializable dictionaries."""
        return [
            {
                "id": rule.id,
                "pattern": rule.pattern,
                "pattern_type": rule.pattern_type,
                "category": rule.category.value,
                "risk_level": rule.risk_level.value,
                "enabled": rule.enabled,
                "description": rule.description,
                "source": rule.source,
            }
            for rule in self.get_all_rules(category)
        ]

    def import_rules(self, category: RiskCategory, rules_data: list[dict]) -> int:
        """Add supplied rules to memory for compatibility with existing callers."""
        with self._lock:
            for item in rules_data:
                self._rules.setdefault(category, []).append(
                    Rule(
                        id=item.get("id", f"import-{datetime.now().timestamp()}"),
                        pattern=item["pattern"],
                        pattern_type=item.get("pattern_type", "keyword"),
                        category=category,
                        risk_level=RiskLevel(item.get("risk_level", "high")),
                        enabled=item.get("enabled", True),
                        description=item.get("description", ""),
                        source=item.get("source", ""),
                    )
                )
        return len(rules_data)
