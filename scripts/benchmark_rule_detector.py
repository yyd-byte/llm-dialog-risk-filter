#!/usr/bin/env python3
"""Benchmark warmed Aho-Corasick detection against the configured rule library."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.detection.rule_detector import RuleDetector  # noqa: E402
from src.rules.manager import RuleManager  # noqa: E402
from src.rules.repository import RuleRepository  # noqa: E402


def measure(detector: RuleDetector, text: str, iterations: int) -> dict[str, float]:
    """Measure warmed detector latency for a representative text."""
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        detector.detect(text)
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "average_ms": statistics.mean(samples),
        "p95_ms": sorted(samples)[max(0, int(len(samples) * 0.95) - 1)],
    }


def main() -> None:
    """Build the production matcher and print warm-detection timing summaries."""
    parser = argparse.ArgumentParser(description="规则检测 Aho-Corasick 性能基准")
    parser.add_argument("--rules-dir", default=PROJECT_ROOT / "config" / "rules", type=Path)
    parser.add_argument("--iterations", default=200, type=int)
    args = parser.parse_args()

    build_start = time.perf_counter()
    manager = RuleManager(RuleRepository(str(args.rules_dir)))
    detector = RuleDetector(manager)
    build_ms = (time.perf_counter() - build_start) * 1000
    rule_count = len(manager.get_enabled_rules())

    workloads = {
        "short_no_match": "Python 装饰器和类型注解如何配合使用？",
        "long_no_match": "这是一段用于规则性能测试的正常技术说明。" * 100,
    }
    print(f"rules={rule_count} build_ms={build_ms:.2f} iterations={args.iterations}")
    for name, text in workloads.items():
        result = measure(detector, text, args.iterations)
        print(
            f"{name}: chars={len(text)} avg_ms={result['average_ms']:.3f} "
            f"p95_ms={result['p95_ms']:.3f}"
        )


if __name__ == "__main__":
    main()
