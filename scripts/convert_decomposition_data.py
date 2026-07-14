#!/usr/bin/env python3
"""Convert funNLP chaizi-jt.txt to decomposition_map.yaml.

Reads the character decomposition dictionary and inverts it:
original: 赌	贝 者
inverted: 贝者 → 赌, 贝 者 → 赌, 者贝 → 赌

Also generates space-separated and reversed-order variants to catch
attackers who write components in different orders.
"""

import os
import sys
import yaml
from pathlib import Path
from collections import defaultdict


def _resolve_tmp() -> Path:
    """Resolve /tmp on platforms where Python doesn't see it (e.g. Git Bash on Windows)."""
    p = Path("/tmp")
    if p.exists():
        return p
    # Git Bash on Windows: /tmp maps to %TEMP%
    win_tmp = os.environ.get("TEMP") or os.environ.get("TMP")
    if win_tmp:
        return Path(win_tmp)
    return p


FUNNLP_DIR = Path(os.environ.get(
    "FUNNLP_DIR",
    str(_resolve_tmp() / "funNLP" / "data" / "拆字词库"),
))
CHAIZI_PATH = FUNNLP_DIR / "chaizi-jt.txt"
OUTPUT_PATH = Path("config/decomposition_map.yaml")


def main() -> None:
    if not CHAIZI_PATH.exists():
        raise FileNotFoundError(
            f"chaizi-jt.txt not found at {CHAIZI_PATH}\n"
            f"  Hint: set $FUNNLP_DIR to the directory containing chaizi-jt.txt, "
            f"or run: export FUNNLP_DIR='/path/to/拆字词库'"
        )

    # decomposition_map: "拆字组合" → "原字"
    # Multiple component strings may map to the same character
    decomposition_map: dict[str, str] = {}

    with open(CHAIZI_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            char = parts[0]          # the original character
            # parts[1], parts[2], ... are different decompositions
            for decomp in parts[1:]:
                decomp = decomp.strip()
                if not decomp:
                    continue
                components = decomp.split()  # split on space → list of components
                if len(components) < 2:
                    continue
                # Variant 1: no spaces, original order
                key1 = "".join(components)
                # Variant 2: no spaces, reversed order
                key2 = "".join(reversed(components))
                for key in (key1, key2):
                    if key not in decomposition_map:
                        decomposition_map[key] = char

    # Remove keys that are single characters (no decomposition actually needed)
    decomposition_map = {k: v for k, v in decomposition_map.items() if len(k) >= 2}

    # Write YAML
    header = (
        "# =============================================================================\n"
        "# 拆字 → 原字 反向映射表\n"
        "# 从 funNLP 拆字词库 (chaizi-jt.txt) 自动生成\n"
        "# 用于检测拆分汉字绕过（如 木仓→枪 女子→好）\n"
        "#\n"
        "# 格式: \"拆字部件组合\": \"原字\"\n"
        "# 包含原始顺序和逆序两种变体\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            decomposition_map,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    print(f"Generated {OUTPUT_PATH} with {len(decomposition_map)} entries")


if __name__ == "__main__":
    main()
