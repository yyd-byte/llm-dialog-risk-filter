#!/usr/bin/env python3
"""Import reviewed tagged sensitive-word data into local YAML rule libraries."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "rules" / "houbb_sensitive_word_mapping.yaml"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "config" / "rules" / "houbb_sensitive_word_manifest.yaml"
CATEGORY_ORDER = ("sexual", "violent", "advertising", "sensitive")
SOURCE_PREFIX = "houbb:sensitive-word-data@"
TAG_PATTERN = re.compile(r"^[0-4](?:,[0-4])*$")
CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ImportCandidate:
    """Represent one validated upstream candidate ready for local import."""

    category: str
    pattern: str
    rule_id: str
    source: str


def load_yaml(path: Path) -> dict:
    """Load a YAML mapping from path."""
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def dump_yaml(data: dict) -> str:
    """Serialize YAML consistently for reproducible imports."""
    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def file_sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of path."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_pattern(pattern: str) -> str:
    """Return the key used for case-insensitive keyword deduplication."""
    return pattern.strip().casefold()


def rule_id_for(category: str, pattern: str) -> str:
    """Build a stable imported-rule ID from category and pattern digest."""
    digest = hashlib.sha256(pattern.encode("utf-8")).hexdigest()[:16]
    return f"houbb-{category}-{digest}"


def parse_candidates(
    input_path: Path,
    policy: dict,
) -> tuple[list[ImportCandidate], Counter[str]]:
    """Parse approved tagged records while aggregating all rejected records."""
    source_config = policy["source"]
    defaults = policy["import_defaults"]
    category_by_signature = policy["tag_signature_categories"]
    min_pattern_length = int(policy["safety"]["min_pattern_length"])
    source = (
        f"{SOURCE_PREFIX}{source_config['commit']}:"
        f"{source_config['resource_path']}#{file_sha256(input_path)[:16]}"
    )
    candidates: list[ImportCandidate] = []
    quarantined: Counter[str] = Counter()
    seen_patterns: set[str] = set()

    for raw_line in input_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            quarantined["blank"] += 1
            continue

        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) != 2 or not TAG_PATTERN.fullmatch(parts[1]):
            quarantined["malformed"] += 1
            continue

        pattern, signature = parts
        category = category_by_signature.get(signature)
        if category is None:
            quarantined["unmapped_tag_signature"] += 1
            continue
        if category not in CATEGORY_ORDER:
            quarantined["invalid_local_category"] += 1
            continue
        if CONTROL_PATTERN.search(pattern) or any(char.isspace() for char in pattern):
            quarantined["unsafe_pattern"] += 1
            continue
        if len(pattern) < min_pattern_length:
            quarantined["unsafe_short_pattern"] += 1
            continue

        pattern_key = normalized_pattern(pattern)
        if pattern_key in seen_patterns:
            quarantined["duplicate_upstream_pattern"] += 1
            continue
        seen_patterns.add(pattern_key)
        candidates.append(
            ImportCandidate(
                category=category,
                pattern=pattern,
                rule_id=rule_id_for(category, pattern),
                source=source,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.category, candidate.rule_id))
    if defaults.get("pattern_type") != "keyword":
        raise ValueError("Only keyword imports are supported")
    return candidates, quarantined


def build_rule_files(
    rules_dir: Path,
    candidates: list[ImportCandidate],
    policy: dict,
    prune_owned: bool,
) -> tuple[dict[Path, str], Counter[str], Counter[str], list[ImportCandidate]]:
    """Merge candidates without modifying manual rules or foreign imported rules."""
    candidates_by_category = {category: [] for category in CATEGORY_ORDER}
    for candidate in candidates:
        candidates_by_category[candidate.category].append(candidate)

    rendered: dict[Path, str] = {}
    imported_counts: Counter[str] = Counter()
    quarantined: Counter[str] = Counter()
    generated_candidates: list[ImportCandidate] = []
    defaults = policy["import_defaults"]

    for category in CATEGORY_ORDER:
        path = rules_dir / f"{category}.yaml"
        content = load_yaml(path)
        rules = content.get("rules")
        if not isinstance(rules, list):
            raise ValueError(f"rules must be a list: {path}")

        existing_patterns: dict[str, dict] = {}
        retained_rules: list[dict] = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise ValueError(f"rule must be a mapping: {path}")
            is_owned = str(rule.get("source", "")).startswith(SOURCE_PREFIX)
            if prune_owned and is_owned:
                continue
            retained_rules.append(rule)
            if rule.get("pattern_type", "keyword") == "keyword":
                existing_patterns.setdefault(normalized_pattern(str(rule.get("pattern", ""))), rule)

        generated_rules: list[dict] = []
        for candidate in candidates_by_category[category]:
            existing = existing_patterns.get(normalized_pattern(candidate.pattern))
            if existing is not None:
                if existing.get("id") == candidate.rule_id and str(
                    existing.get("source", "")
                ).startswith(SOURCE_PREFIX):
                    generated_candidates.append(candidate)
                    imported_counts[category] += 1
                else:
                    quarantined["existing_pattern_conflict"] += 1
                continue
            generated_rules.append(
                {
                    "id": candidate.rule_id,
                    "pattern": candidate.pattern,
                    "pattern_type": defaults["pattern_type"],
                    "risk_level": defaults["risk_level"],
                    "enabled": defaults["enabled"],
                    "description": "Imported tagged sensitive-word entry",
                    "source": candidate.source,
                }
            )
            generated_candidates.append(candidate)
            imported_counts[category] += 1

        content["rules"] = retained_rules + generated_rules
        if candidates_by_category[category] or (prune_owned and len(retained_rules) != len(rules)):
            rendered[path] = dump_yaml(content)

    return rendered, imported_counts, quarantined, generated_candidates


def build_manifest(
    policy: dict,
    input_path: Path,
    candidates: list[ImportCandidate],
    imported_counts: Counter[str],
    quarantined: Counter[str],
) -> dict:
    """Build an audit manifest that excludes raw upstream patterns."""
    return {
        "schema_version": 1,
        "policy_version": policy["policy_version"],
        "source": {
            **policy["source"],
            "input_sha256": file_sha256(input_path),
        },
        "license": policy["license"],
        "imported_counts": {category: imported_counts[category] for category in CATEGORY_ORDER},
        "imported_rules": [
            {
                "id": candidate.rule_id,
                "category": candidate.category,
                "pattern_sha256": hashlib.sha256(candidate.pattern.encode("utf-8")).hexdigest(),
            }
            for candidate in candidates
            if imported_counts[candidate.category]
        ],
        "quarantine_counts": dict(sorted(quarantined.items())),
    }


def write_files(rendered: dict[Path, str], manifest_path: Path, manifest: dict) -> None:
    """Write generated rule files and manifest after an explicit apply request."""
    for path, content in rendered.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8", newline="\n")


def verify_expected_files(rendered: dict[Path, str], manifest_path: Path, manifest: dict) -> bool:
    """Return whether committed output exactly matches the deterministic import."""
    expected = {**rendered, manifest_path: dump_yaml(manifest)}
    return all(
        path.exists() and path.read_text(encoding="utf-8") == content
        for path, content in expected.items()
    )


def main() -> None:
    """Run the tagged-word import CLI."""
    parser = argparse.ArgumentParser(description="导入经审核的上游标签敏感词数据")
    parser.add_argument("--input", type=Path, required=True, help="固定版本的标签词表文件")
    parser.add_argument(
        "--policy", type=Path, default=DEFAULT_POLICY_PATH, help="本地映射策略 YAML"
    )
    parser.add_argument(
        "--rules-dir", type=Path, default=PROJECT_ROOT / "config" / "rules", help="规则目录"
    )
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH, help="生成的审计清单"
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--apply", action="store_true", help="写入规则与清单")
    action_group.add_argument("--check", action="store_true", help="校验规则与清单是否可复现")
    parser.add_argument(
        "--prune-owned", action="store_true", help="仅在 apply 时清理本导入器的旧规则"
    )
    args = parser.parse_args()

    if args.prune_owned and not args.apply:
        parser.error("--prune-owned requires --apply")
    if not args.input.is_file():
        parser.error(f"input file not found: {args.input}")
    if not args.policy.is_file():
        parser.error(f"policy file not found: {args.policy}")

    policy = load_yaml(args.policy)
    expected_hash = policy["source"].get("sha256", "")
    actual_hash = file_sha256(args.input)
    if expected_hash != actual_hash:
        parser.error("input SHA-256 does not match the reviewed mapping policy")

    candidates, parse_quarantined = parse_candidates(args.input, policy)
    rendered, imported_counts, merge_quarantined, generated_candidates = build_rule_files(
        args.rules_dir,
        candidates,
        policy,
        args.prune_owned,
    )
    quarantined = parse_quarantined + merge_quarantined
    manifest = build_manifest(
        policy,
        args.input,
        generated_candidates,
        imported_counts,
        quarantined,
    )

    if args.check:
        if not verify_expected_files(rendered, args.manifest, manifest):
            print("CHECK FAILED: rule files or manifest are not reproducible", file=sys.stderr)
            sys.exit(1)
        print("CHECK OK: rules and manifest are reproducible")
        return

    if args.apply:
        write_files(rendered, args.manifest, manifest)
        print("APPLIED: reviewed tagged-word candidates merged into local YAML rules")
    else:
        print("DRY RUN: no files were changed")
    print(f"Candidates: {len(candidates)}")
    print(f"Imported by category: {dict(manifest['imported_counts'])}")
    print(f"Quarantine counts: {dict(sorted(quarantined.items()))}")


if __name__ == "__main__":
    main()
