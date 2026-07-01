#!/usr/bin/env python3
"""Initialize rule library with placeholder rules.

Creates the four category rule files with placeholder/template content.
Run this once after cloning the repository.

Usage:
    python scripts/init_rules.py
"""

import sys
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parent.parent / "config" / "rules"

CATEGORIES = {
    "sexual": {
        "label": "色情低俗",
        "description": "检测色情、低俗、性暗示等违规内容",
        "rules": [
            {
                "id": "sexual-kw-001",
                "pattern": "[占位]性暗示词汇A",
                "pattern_type": "keyword",
                "risk_level": "high",
                "enabled": True,
                "description": "直接性暗示表达",
            },
            {
                "id": "sexual-re-001",
                "pattern": r"[占位]正则表达式A",
                "pattern_type": "regex",
                "risk_level": "high",
                "enabled": True,
                "description": "变体性暗示模式",
            },
        ],
    },
    "violent": {
        "label": "暴力危险",
        "description": "检测暴力、威胁、自残、危险行为等违规内容",
        "rules": [
            {
                "id": "violent-kw-001",
                "pattern": "[占位]暴力威胁词汇A",
                "pattern_type": "keyword",
                "risk_level": "high",
                "enabled": True,
                "description": "直接暴力威胁",
            },
            {
                "id": "violent-re-001",
                "pattern": r"[占位]暴力正则表达式A",
                "pattern_type": "regex",
                "risk_level": "high",
                "enabled": True,
                "description": "暴力变体表达",
            },
        ],
    },
    "advertising": {
        "label": "广告引流",
        "description": "检测广告推广、联系方式引流、重复营销话术等违规内容",
        "rules": [
            {
                "id": "ad-kw-001",
                "pattern": "[占位]联系方式模式A",
                "pattern_type": "keyword",
                "risk_level": "medium",
                "enabled": True,
                "description": "手机号/微信号引流",
            },
            {
                "id": "ad-re-001",
                "pattern": r"[占位]URL正则A",
                "pattern_type": "regex",
                "risk_level": "medium",
                "enabled": True,
                "description": "外部链接引流",
            },
        ],
    },
    "sensitive": {
        "label": "敏感话术",
        "description": "检测政治敏感、违法违规、谣言等敏感话术",
        "rules": [
            {
                "id": "sens-kw-001",
                "pattern": "[占位]敏感话题词汇A",
                "pattern_type": "keyword",
                "risk_level": "high",
                "enabled": True,
                "description": "政治敏感话题",
            },
            {
                "id": "sens-re-001",
                "pattern": r"[占位]敏感正则表达式A",
                "pattern_type": "regex",
                "risk_level": "medium",
                "enabled": True,
                "description": "边界敏感内容",
            },
        ],
    },
}


def main():
    """Initialize all rule files."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    for category, data in CATEGORIES.items():
        filepath = RULES_DIR / f"{category}.yaml"
        content = {
            "category": category,
            "label": data["label"],
            "description": data["description"],
            "rules": data["rules"],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(content, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        print(f"✓ 已创建: {filepath} ({len(data['rules'])} 条规则)")

    print(f"\n✅ 规则库初始化完成，共 {len(CATEGORIES)} 个类别")


if __name__ == "__main__":
    main()