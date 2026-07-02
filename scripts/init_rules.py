#!/usr/bin/env python3
"""Initialize rule library with real detection rules.

Creates the four category rule files with practical keyword/regex patterns.
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
                "id": "sexual-kw-001", "pattern": "裸聊", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "裸聊邀请",
            },
            {
                "id": "sexual-kw-002", "pattern": "约炮", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "约炮",
            },
            {
                "id": "sexual-kw-003", "pattern": "一夜情", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "一夜情",
            },
            {
                "id": "sexual-re-001", "pattern": "[色性][爱交情欲]", "pattern_type": "regex",
                "risk_level": "medium", "enabled": True, "description": "色情组合词",
            },
            {
                "id": "sexual-re-002", "pattern": "[操草日][你妳死他妈]", "pattern_type": "regex",
                "risk_level": "high", "enabled": True, "description": "侮辱性脏话组合",
            },
        ],
    },
    "violent": {
        "label": "暴力危险",
        "description": "检测暴力、威胁、自残、危险行为等违规内容",
        "rules": [
            {
                "id": "violent-kw-001", "pattern": "杀了你", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "死亡威胁",
            },
            {
                "id": "violent-kw-002", "pattern": "自杀", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "自杀倾向",
            },
            {
                "id": "violent-kw-003", "pattern": "恐怖袭击", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "恐怖主义",
            },
            {
                "id": "violent-re-001", "pattern": "[杀砍打弄废揍][死了死你]", "pattern_type": "regex",
                "risk_level": "high", "enabled": True, "description": "暴力威胁组合",
            },
            {
                "id": "violent-re-002", "pattern": "我?[要去想]死", "pattern_type": "regex",
                "risk_level": "medium", "enabled": True, "description": "自杀倾向表达",
            },
        ],
    },
    "advertising": {
        "label": "广告引流",
        "description": "检测广告推广、联系方式引流、重复营销话术等违规内容",
        "rules": [
            {
                "id": "ad-kw-001", "pattern": "加我微信", "pattern_type": "keyword",
                "risk_level": "medium", "enabled": True, "description": "微信号引流",
            },
            {
                "id": "ad-kw-002", "pattern": "加微信", "pattern_type": "keyword",
                "risk_level": "medium", "enabled": True, "description": "微信号引流",
            },
            {
                "id": "ad-kw-003", "pattern": "扫码", "pattern_type": "keyword",
                "risk_level": "medium", "enabled": True, "description": "二维码引流",
            },
            {
                "id": "ad-kw-004", "pattern": "刷单", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "刷单诈骗",
            },
            {
                "id": "ad-re-001", "pattern": "1[3-9]\\d{9}", "pattern_type": "regex",
                "risk_level": "medium", "enabled": True, "description": "中国大陆手机号",
            },
            {
                "id": "ad-re-002", "pattern": "https?://\\S+", "pattern_type": "regex",
                "risk_level": "medium", "enabled": True, "description": "外部URL链接",
            },
        ],
    },
    "sensitive": {
        "label": "敏感话术",
        "description": "检测政治敏感、违法违规、谣言等敏感话术",
        "rules": [
            {
                "id": "sens-kw-001", "pattern": "翻墙", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "网络违法",
            },
            {
                "id": "sens-kw-002", "pattern": "贩卖毒品", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "毒品违法",
            },
            {
                "id": "sens-kw-003", "pattern": "赌博", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "赌博",
            },
            {
                "id": "sens-kw-004", "pattern": "洗钱", "pattern_type": "keyword",
                "risk_level": "high", "enabled": True, "description": "洗钱",
            },
            {
                "id": "sens-re-001", "pattern": "[贩买吸]毒", "pattern_type": "regex",
                "risk_level": "high", "enabled": True, "description": "毒品相关",
            },
            {
                "id": "sens-re-002", "pattern": "[赌博彩][场博]", "pattern_type": "regex",
                "risk_level": "high", "enabled": True, "description": "赌博相关",
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

        print(f"已创建: {filepath} ({len(data['rules'])} 条规则)")

    total = sum(len(d["rules"]) for d in CATEGORIES.values())
    print(f"\n规则库初始化完成，共 {len(CATEGORIES)} 个类别、{total} 条规则")


if __name__ == "__main__":
    main()