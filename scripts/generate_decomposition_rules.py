#!/usr/bin/env python3
"""Generate decomposition-variant rules for existing 2-character Chinese keywords.

Path A: Pre-compute decomposition variants for each 2-character Chinese keyword
in the rule base, then inject them as additional keyword rules.

Strategy:
- Only process keywords with exactly 2 Chinese characters (avoid Cartesian explosion)
- Use only the first decomposition variant per character (from decomposition_map.yaml)
- Generate exactly 1 variant per keyword

Example:
    Rule "赌博" -> decompose "赌"="贝者", "博"="十甫寸"
    -> Generate rule: "贝者十甫寸"

Total expected: 300-600 new rules across all 4 categories.
"""

import yaml
from pathlib import Path


RULES_DIR = Path("config/rules")
DECOMP_MAP_PATH = Path("config/decomposition_map.yaml")

# Categories to process
CATEGORIES = ["sexual", "violent", "advertising", "sensitive"]


def load_first_decomposition(path: Path) -> dict[str, str]:
    """Load the decomposition map and keep only the FIRST variant per character.

    The decomposition_map.yaml maps component_strings to original chars.
    We invert it: for each char, pick the first (shortest) component string.

    Returns: {char: first_component_string}
    Example: {"赌": "贝者", "博": "十甫寸"}
    """
    with open(path, "r", encoding="utf-8") as f:
        decomp_to_char: dict[str, str] = yaml.safe_load(f) or {}

    char_decomp: dict[str, str] = {}
    for decomp_str, char in decomp_to_char.items():
        decomp_str = str(decomp_str)
        char = str(char)
        # Only use non-spaced variants with >=2 chars
        if " " in decomp_str or len(decomp_str) < 2:
            continue
        # Keep first (shortest) decomposition for each char
        if char not in char_decomp:
            char_decomp[char] = decomp_str
        else:
            # Prefer shorter decomposition strings
            if len(decomp_str) < len(char_decomp[char]):
                char_decomp[char] = decomp_str

    return char_decomp


def main() -> None:
    if not DECOMP_MAP_PATH.exists():
        raise FileNotFoundError(
            f"{DECOMP_MAP_PATH} not found. Run "
            "scripts/convert_decomposition_data.py first."
        )

    char_decomp = load_first_decomposition(DECOMP_MAP_PATH)
    print(f"Loaded {len(char_decomp)} characters with decomposition variants")

    total_added = 0

    for category in CATEGORIES:
        rule_file = RULES_DIR / f"{category}.yaml"
        if not rule_file.exists():
            print(f"  {category}: file not found, skipping")
            continue

        with open(rule_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        existing_rules = data.get("rules", [])
        existing_patterns = {r["pattern"] for r in existing_rules
                             if r.get("pattern")}
        existing_ids = {r.get("id", "") for r in existing_rules}

        new_rules = []
        for rule in existing_rules:
            pattern = rule.get("pattern", "")
            pattern_type = rule.get("pattern_type", "keyword")
            # Only process keyword rules
            if pattern_type != "keyword":
                continue
            # Only decompose patterns with exactly 2 Chinese characters
            chinese_chars = [ch for ch in pattern
                             if "一" <= ch <= "鿿"
                             or "㐀" <= ch <= "䶿"]
            if len(chinese_chars) != 2:
                continue

            # Generate 1 decomposition variant: decompose both chars
            variant = "".join(char_decomp.get(ch, ch) for ch in chinese_chars)
            # Skip if no decomposition occurred (variant == original)
            if variant == pattern:
                continue
            # Skip if already exists as a pattern
            if variant in existing_patterns:
                continue

            new_rules.append({
                "id": f"{rule['id']}-dec",
                "pattern": variant,
                "pattern_type": "keyword",
                "risk_level": rule.get("risk_level", "medium"),
                "enabled": True,
                "description": (
                    f"拆字绕过: {pattern} -> {variant} "
                    f"(source: decomposition, parent: {rule['id']})"
                ),
                "source": "decomposition",
            })
            existing_patterns.add(variant)

        if new_rules:
            existing_rules.extend(new_rules)
            data["rules"] = existing_rules

            with open(rule_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    data, f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            print(f"  {category}: added {len(new_rules)} decomp rules")
            total_added += len(new_rules)
        else:
            print(f"  {category}: no new decomp rules")

    print(f"\nTotal new decomposition rules: {total_added}")


if __name__ == "__main__":
    main()
