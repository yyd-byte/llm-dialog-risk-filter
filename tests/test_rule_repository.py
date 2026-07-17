"""Tests for YAML rule repository persistence."""

from pathlib import Path

import yaml

from src.decision.models import RiskCategory, RiskLevel
from src.rules.manager import RuleManager
from src.rules.models import Rule
from src.rules.repository import RuleRepository


class TestRuleRepository:
    """Verify all persisted rule fields survive repository round trips."""

    def test_round_trip_preserves_source(self, tmp_path: Path):
        """Load, save, and reload a rule's source provenance."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        for category in RiskCategory:
            (rules_dir / f"{category.value}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "category": category.value,
                        "label": category.value,
                        "description": "test",
                        "rules": [],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        (rules_dir / "sensitive.yaml").write_text(
            yaml.safe_dump(
                {
                    "category": "sensitive",
                    "label": "test",
                    "description": "test",
                    "rules": [
                        {
                            "id": "imported-1",
                            "pattern": "fixture-pattern",
                            "pattern_type": "keyword",
                            "risk_level": "medium",
                            "enabled": True,
                            "description": "fixture",
                            "source": "houbb:sensitive-word-data@test",
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        repository = RuleRepository(str(rules_dir))
        loaded = repository.load_category(RiskCategory.SENSITIVE)
        repository.save_category(RiskCategory.SENSITIVE, loaded)
        reloaded = repository.load_category(RiskCategory.SENSITIVE)

        assert len(reloaded) == 1
        assert reloaded[0].source == "houbb:sensitive-word-data@test"
        assert reloaded[0].risk_level == RiskLevel.MEDIUM

    def test_manager_export_import_preserves_source(self, tmp_path: Path):
        """Export and re-import provenance through the manager API."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        for category in RiskCategory:
            (rules_dir / f"{category.value}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "category": category.value,
                        "label": category.value,
                        "description": "test",
                        "rules": [],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

        manager = RuleManager(RuleRepository(str(rules_dir)))
        manager.add_rule(
            Rule(
                id="source-rule",
                pattern="fixture-pattern",
                category=RiskCategory.SENSITIVE,
                source="reviewed-source",
            )
        )
        exported = manager.export_rules(RiskCategory.SENSITIVE)

        assert exported[0]["source"] == "reviewed-source"

        receiving_manager = RuleManager(RuleRepository(str(rules_dir)))
        receiving_manager.import_rules(RiskCategory.SENSITIVE, exported)
        imported = receiving_manager.get_rule_by_id("source-rule")

        assert imported is not None
        assert imported.source == "reviewed-source"
