#!/usr/bin/env python3
"""Convert funNLP fanjian_suoyin.txt to traditional_simplified.yaml.

Extracts only the entries where traditional ≠ simplified (5,908 pairs).
"""

import yaml
from pathlib import Path


OUTPUT_PATH = Path("config/traditional_simplified.yaml")


def _find_fanjian() -> Path:
    """Try several likely locations for fanjian_suoyin.txt."""
    candidates = [
        Path("/tmp/funNLP/data/繁简体转换词库/fanjian_suoyin.txt"),
        Path.home() / "AppData/Local/Temp/funNLP/data/繁简体转换词库/fanjian_suoyin.txt",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"fanjian_suoyin.txt not found. Tried:\n"
        + "\n".join(f"  - {c}" for c in candidates)
    )


def main() -> None:
    fanjian_path = _find_fanjian()

    ts_map: dict[str, str] = {}
    same_count = 0

    with open(fanjian_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            traditional = parts[0].strip()
            simplified = parts[1].strip()
            if traditional != simplified and traditional and simplified:
                ts_map[traditional] = simplified
            else:
                same_count += 1

    header = (
        "# =============================================================================\n"
        "# 繁体中文 → 简体中文 映射表\n"
        "# 从 funNLP 繁简体转换词库自动生成\n"
        "# 仅包含有差异的繁简对（同字行列不计）\n"
        "#\n"
        "# 格式: \"繁体\": \"简体\"\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            ts_map,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    print(f"Generated {OUTPUT_PATH} with {len(ts_map)} differing pairs "
          f"({same_count} same-char lines skipped)")


if __name__ == "__main__":
    main()
