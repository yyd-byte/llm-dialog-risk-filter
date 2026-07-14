#!/usr/bin/env python3
"""Convert funNLP abbreviation dataset to abbreviation_map.yaml.

Reads train/dev/test sets, strips POS tags, and produces a clean
abbreviation → full-form mapping. Handles entries with the format:
  禁毒办: 禁毒/vn 办公室/n
  →
  禁毒办: 禁毒办公室
"""

import yaml
from pathlib import Path
import re


OUTPUT_PATH = Path("config/abbreviation_map.yaml")

# Try multiple locations for funNLP data (cross-platform)
_CANDIDATE_DIRS = [
    Path("/tmp/funNLP/data/中文缩写库"),                     # Linux / macOS
    Path.home() / "AppData/Local/Temp/funNLP/data/中文缩写库",  # Windows (Git Bash)
]

ABBREV_DIR: Path | None = None
for d in _CANDIDATE_DIRS:
    if d.exists():
        ABBREV_DIR = d
        break

if ABBREV_DIR is None:
    print(f"Error: funNLP data not found. Tried: {[str(p) for p in _CANDIDATE_DIRS]}")
    raise SystemExit(1)


def remove_pos_tags(text: str) -> str:
    """Remove POS tags like /vn, /n, /nr from a word."""
    return re.sub(r"/[a-zA-Z]+", "", text)


def main() -> None:
    all_entries: dict[str, str] = {}

    for filename in ["train_set.txt", "dev_set.txt", "test_set.txt"]:
        filepath = ABBREV_DIR / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n").rstrip("\r")
                if not line or ":" not in line:
                    continue
                # Format: "abbrev: word1/POS word2/POS ..."
                abbrev, rest = line.split(":", 1)
                abbrev = abbrev.strip()
                rest = rest.strip()

                # Skip entries where abbreviation starts with "n:" (annotation error)
                if abbrev == "n":
                    continue

                # Remove POS tags and join
                words = rest.split()
                full_form = "".join(remove_pos_tags(w) for w in words)

                if abbrev and full_form and len(abbrev) >= 2:
                    # Keep the first occurrence (train > dev > test)
                    if abbrev not in all_entries:
                        all_entries[abbrev] = full_form

    # Sort by key length descending for longest-match-first replacement
    sorted_entries = dict(
        sorted(all_entries.items(), key=lambda x: len(x[0]), reverse=True)
    )

    header = (
        "# =============================================================================\n"
        "# 中文缩写 → 完整形式 映射表\n"
        "# 从 funNLP 中文缩写库自动生成\n"
        "# 用于在 normalizer 中将缩写展开为完整形式\n"
        "#\n"
        "# 格式: \"缩写\": \"完整形式\"\n"
        "# 缩写 ≥2 字符，完整形式去除词性标签\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            sorted_entries,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    print(f"Generated {OUTPUT_PATH} with {len(sorted_entries)} entries")


if __name__ == "__main__":
    main()
