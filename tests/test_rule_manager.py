"""Tests for versioned and persisted rule-manager behavior."""

from pathlib import Path

import pytest
import yaml

from src.decision.models import RiskCategory
from src.rules.manager import RuleManager, RuleVersionConflictError
from src.rules.repository import RuleRepository


def build_manager(tmp_path: Path) -> tuple[RuleManager, Path]:
    """Create a complete minimal rule library for management tests."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    for category in RiskCategory:
        rules = []
        if category == RiskCategory.SENSITIVE:
            rules = [
                {
                    "id": "managed-rule",
                    "pattern": "fixture-pattern",
                    "pattern_type": "keyword",
                    "risk_level": "medium",
                    "enabled": True,
                    "description": "fixture",
                    "source": "manual",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            ]
        (rules_dir / f"{category.value}.yaml").write_text(
            yaml.safe_dump(
                {
                    "category": category.value,
                    "label": category.value,
                    "description": "",
                    "rules": rules,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    return RuleManager(RuleRepository(str(rules_dir))), rules_dir


class TestRuleManager:
    """Verify managed rule state is paginated, versioned, and durable."""

    def test_set_enabled_persists_and_changes_version(self, tmp_path: Path):
        """Persist an explicit enabled state and retain rule provenance fields."""
        manager, rules_dir = build_manager(tmp_path)
        before = manager.rebuild_version()
        rule, after, previous = manager.set_rule_enabled("managed-rule", False, before)

        assert previous is True
        assert rule.enabled is False
        assert after != before
        reloaded = RuleManager(RuleRepository(str(rules_dir))).get_rule_by_id("managed-rule")
        assert reloaded is not None
        assert reloaded.enabled is False
        assert reloaded.source == "manual"
        assert reloaded.updated_at != "2026-01-01T00:00:00"

    def test_stale_version_does_not_change_rule(self, tmp_path: Path):
        """Reject a stale optimistic-concurrency version before persistence."""
        manager, _ = build_manager(tmp_path)
        with pytest.raises(RuleVersionConflictError):
            manager.set_rule_enabled("managed-rule", False, "sha256:stale")
        assert manager.get_rule_by_id("managed-rule").enabled is True

    def test_list_rules_filters_and_pages(self, tmp_path: Path):
        """Filter by source/status and return a stable page."""
        manager, _ = build_manager(tmp_path)
        rules, total = manager.list_rules(source="manual", enabled=True, page=1, page_size=10)
        assert total == 1
        assert [rule.id for rule in rules] == ["managed-rule"]
