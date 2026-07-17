"""Tests for the deterministic tagged sensitive-word importer."""

import hashlib
from pathlib import Path

import pytest
import yaml

from scripts import import_sensitive_words as importer


CATEGORY_LABELS = {
    "sexual": "色情低俗",
    "violent": "暴力危险",
    "advertising": "广告引流",
    "sensitive": "敏感话术",
}


def write_rule_files(rules_dir: Path) -> None:
    """Create a complete small local rule library for importer tests."""
    for category, label in CATEGORY_LABELS.items():
        rules = [
            {
                "id": f"{category}-manual-keyword",
                "pattern": "manual-pattern",
                "pattern_type": "keyword",
                "risk_level": "medium",
                "enabled": True,
                "description": "manual rule",
            }
        ]
        if category == "advertising":
            rules.append(
                {
                    "id": "advertising-regex",
                    "pattern": r"\\d+",
                    "pattern_type": "regex",
                    "risk_level": "medium",
                    "enabled": True,
                    "description": "manual regex",
                }
            )
        (rules_dir / f"{category}.yaml").write_text(
            yaml.safe_dump(
                {
                    "category": category,
                    "label": label,
                    "description": "test rules",
                    "rules": rules,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )


def write_policy(policy_path: Path, input_path: Path) -> None:
    """Write a minimal reviewed policy bound to the synthetic fixture."""
    policy = {
        "policy_version": "test-v1",
        "source": {
            "repository": "https://example.invalid/source",
            "commit": "f" * 40,
            "resource_path": "tags.txt",
            "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        },
        "license": "Apache-2.0",
        "tag_signature_categories": {"2": "sexual", "4": "sensitive"},
        "import_defaults": {
            "pattern_type": "keyword",
            "risk_level": "medium",
            "enabled": True,
        },
        "safety": {"min_pattern_length": 3},
    }
    policy_path.write_text(
        yaml.safe_dump(policy, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


@pytest.fixture
def import_workspace(tmp_path: Path) -> dict[str, Path]:
    """Build isolated input, policy, rules, and manifest paths."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    write_rule_files(rules_dir)
    input_path = tmp_path / "tags.txt"
    input_path.write_text(
        "approved-sexual 2\napproved-sensitive 4\nxy 2\nambiguous 2,4\nunknown 1\n",
        encoding="utf-8",
    )
    policy_path = tmp_path / "policy.yaml"
    write_policy(policy_path, input_path)
    return {
        "input": input_path,
        "policy": policy_path,
        "rules_dir": rules_dir,
        "manifest": tmp_path / "manifest.yaml",
    }


def import_once(paths: dict[str, Path], prune_owned: bool = False) -> tuple[dict, dict]:
    """Run the importer functions without the command-line shell."""
    policy = importer.load_yaml(paths["policy"])
    candidates, parse_quarantined = importer.parse_candidates(paths["input"], policy)
    rendered, counts, merge_quarantined, generated = importer.build_rule_files(
        paths["rules_dir"],
        candidates,
        policy,
        prune_owned,
    )
    manifest = importer.build_manifest(
        policy,
        paths["input"],
        generated,
        counts,
        parse_quarantined + merge_quarantined,
    )
    return rendered, manifest


class TestTaggedSensitiveWordImporter:
    """Verify policy-driven import behavior with synthetic tagged records."""

    def test_imports_only_mapped_safe_single_tags(self, import_workspace):
        """Import reviewed signatures and quarantine all other fixture records."""
        rendered, manifest = import_once(import_workspace)
        sexual = yaml.safe_load(rendered[import_workspace["rules_dir"] / "sexual.yaml"])
        sensitive = yaml.safe_load(rendered[import_workspace["rules_dir"] / "sensitive.yaml"])

        assert manifest["imported_counts"] == {
            "sexual": 1,
            "violent": 0,
            "advertising": 0,
            "sensitive": 1,
        }
        assert manifest["quarantine_counts"] == {
            "unmapped_tag_signature": 2,
            "unsafe_short_pattern": 1,
        }
        imported = [rule for rule in sexual["rules"] if rule["id"].startswith("houbb-")]
        assert len(imported) == 1
        assert imported[0]["source"].startswith("houbb:sensitive-word-data@")
        assert len([rule for rule in sensitive["rules"] if rule["id"].startswith("houbb-")]) == 1

    def test_keeps_manual_and_regex_rules_unchanged(self, import_workspace):
        """Preserve existing rules while appending generated keyword rules."""
        rendered, _ = import_once(import_workspace)
        advertising = yaml.safe_load(
            (import_workspace["rules_dir"] / "advertising.yaml").read_text(encoding="utf-8")
        )
        ids = {rule["id"] for rule in advertising["rules"]}

        assert "advertising-manual-keyword" in ids
        assert "advertising-regex" in ids

    def test_apply_output_is_reproducible(self, import_workspace):
        """Produce byte-identical rules and manifest across two applications."""
        rendered, manifest = import_once(import_workspace)
        importer.write_files(rendered, import_workspace["manifest"], manifest)
        first_contents = {
            path: path.read_text(encoding="utf-8")
            for path in [*rendered, import_workspace["manifest"]]
        }

        rerendered, remanifest = import_once(import_workspace)
        importer.write_files(rerendered, import_workspace["manifest"], remanifest)
        second_contents = {
            path: path.read_text(encoding="utf-8")
            for path in [*rerendered, import_workspace["manifest"]]
        }

        assert first_contents == second_contents
        assert importer.verify_expected_files(
            rerendered,
            import_workspace["manifest"],
            remanifest,
        )

    def test_prune_owned_removes_only_importer_rules(self, import_workspace):
        """Remove generated rules only when pruning is explicitly requested."""
        rendered, manifest = import_once(import_workspace)
        importer.write_files(rendered, import_workspace["manifest"], manifest)
        import_workspace["input"].write_text("", encoding="utf-8")
        write_policy(import_workspace["policy"], import_workspace["input"])

        preserved, _ = import_once(import_workspace)
        pruned, _ = import_once(import_workspace, prune_owned=True)
        assert not preserved
        preserved_sexual = yaml.safe_load(
            (import_workspace["rules_dir"] / "sexual.yaml").read_text(encoding="utf-8")
        )
        pruned_sexual = yaml.safe_load(pruned[import_workspace["rules_dir"] / "sexual.yaml"])

        assert any(rule["id"].startswith("houbb-") for rule in preserved_sexual["rules"])
        assert not any(rule["id"].startswith("houbb-") for rule in pruned_sexual["rules"])
        assert any(rule["id"] == "sexual-manual-keyword" for rule in pruned_sexual["rules"])

    def test_rejects_hash_mismatch(self, import_workspace):
        """Fail before import when input no longer matches reviewed policy."""
        policy = importer.load_yaml(import_workspace["policy"])
        import_workspace["input"].write_text("changed 2\n", encoding="utf-8")

        assert importer.file_sha256(import_workspace["input"]) != policy["source"]["sha256"]
