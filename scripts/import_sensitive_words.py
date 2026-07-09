#!/usr/bin/env python3
"""将 fwwdn/sensitive-stop-words 词库导入为项目 YAML 规则格式。

Usage:
    python scripts/import_sensitive_words.py
"""

import re
import sys
import yaml
from pathlib import Path

# 源词库路径
SOURCE_DIR = Path("C:/Users/gn202/AppData/Local/Temp/sensitive-stop-words")

# 目标 YAML 目录
TARGET_DIR = Path(__file__).resolve().parent.parent / "config" / "rules"

# 文件 → 类别映射
FILE_CATEGORY_MAP = {
    "色情类.txt": "sexual",
    "广告.txt": "advertising",
    "政治类.txt": "sensitive",
    "涉枪涉爆违法信息关键词.txt": "violent",  # 枪支爆炸→暴力危险
}

# 类别标签
CATEGORY_LABELS = {
    "sexual": "色情低俗",
    "violent": "暴力危险",
    "advertising": "广告引流",
    "sensitive": "敏感话术",
}

CATEGORY_DESC = {
    "sexual": "检测色情、低俗、性暗示等违规内容",
    "violent": "检测暴力、威胁、自残、危险行为等违规内容",
    "advertising": "检测广告推广、联系方式引流、重复营销话术等违规内容",
    "sensitive": "检测政治敏感、违法违规、谣言等敏感话术",
}

# 风险等级判断规则
def get_risk_level(category: str, word: str) -> str:
    """根据词的长度和类别判断风险等级。"""
    category_hard_blacklist = {
        "sexual": ["幼", "童", "儿童"],
        "violent": ["炸弹", "恐怖", "杀人"],
        "sensitive": ["领导", "习", "法轮", "六四", "天安门", "藏独", "疆独", "台独"],
        "advertising": [],
    }
    for hard_word in category_hard_blacklist.get(category, []):
        if hard_word in word:
            return "high"
    if len(word) <= 2:
        return "medium"
    return "medium"


def load_words(filepath: Path) -> list[str]:
    """从词库文件读取词汇，去重去空白。"""
    words = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",").strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            # 跳过纯英文、纯数字、过短的词
            if len(line) < 1:
                continue
            words.append(line)
    return list(set(words))  # 去重


def main():
    all_words: dict[str, list[str]] = {
        "sexual": [],
        "violent": [],
        "advertising": [],
        "sensitive": [],
    }

    # 读取所有词
    for filename, category in FILE_CATEGORY_MAP.items():
        filepath = SOURCE_DIR / filename
        if not filepath.exists():
            print(f"SKIP: {filepath} 不存在")
            continue
        words = load_words(filepath)
        all_words[category].extend(words)
        print(f"{filename}: {len(words)} 个词汇 → {category}")

    # 跨类别去重（敏感类优先级最高）
    seen: dict[str, str] = {}  # word → category
    for category in ["sensitive", "sexual", "violent", "advertising"]:
        unique = []
        for word in all_words[category]:
            if word in seen:
                # 如果已在其他类别中，跳到敏感类
                continue
            seen[word] = category
            unique.append(word)
        all_words[category] = sorted(unique, key=lambda w: (len(w), w))

    # 生成各类别 YAML
    for category, words in all_words.items():
        target_path = TARGET_DIR / f"{category}.yaml"

        # 读取已有规则（保留用户自定义的正则规则）
        existing_rules = []
        existing_ids = set()
        existing_patterns = set()
        if target_path.exists():
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for r in data.get("rules", []):
                # 保留所有正则规则 + 少量核心关键词规则
                if r.get("pattern_type") == "regex":
                    existing_rules.append(r)
                    existing_ids.add(r["id"])
                else:
                    existing_patterns.add(r.get("pattern", ""))

        # 生成新规则
        new_rules = list(existing_rules)  # 保留已有正则
        for i, word in enumerate(words):
            # 跳过已存在的关键词
            if word in existing_patterns:
                continue

            prefix_map = {
                "sexual": "sex",
                "violent": "vio",
                "advertising": "adv",
                "sensitive": "sen",
            }
            prefix = prefix_map[category]
            rid = f"{prefix}-kw-{i+1000:03d}"
            rule = {
                "id": rid,
                "pattern": word,
                "pattern_type": "keyword",
                "risk_level": get_risk_level(category, word),
                "enabled": True,
                "description": word,
            }
            new_rules.append(rule)

        # 写入 YAML
        content = {
            "category": category,
            "label": CATEGORY_LABELS[category],
            "description": CATEGORY_DESC[category],
            "rules": new_rules,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(f"# {CATEGORY_LABELS[category]}规则\n")
            # 手动写 YAML 保证格式整洁
            yaml.dump(
                dict(content),
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=120,
            )

        kw_count = sum(1 for r in new_rules if r.get("pattern_type") == "keyword")
        re_count = sum(1 for r in new_rules if r.get("pattern_type") == "regex")
        print(f"写入 {target_path.name}: {kw_count} 关键词 + {re_count} 正则")

    # 汇总
    total = sum(len(w) for w in all_words.values())
    print(f"\n总计 {total} 个词汇，分类完成")


if __name__ == "__main__":
    main()
