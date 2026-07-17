#!/usr/bin/env python3
"""Quantitative evaluation harness for the content filtering pipeline.

Loads labeled test cases, runs each through the full pipeline (normalize →
rule detect → semantic detect → fusion), compares predictions against
expected labels, and computes accuracy / precision / recall / F1 / FPR / FNR.

Usage:
    python scripts/evaluate.py                    # console report
    python scripts/evaluate.py --output markdown  # markdown report
    python scripts/evaluate.py --output json      # machine-readable JSON
    python scripts/evaluate.py --no-semantic      # rules-only (fast)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# ---- Add project root to path ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.decision.fusion import RiskFusion, fusion_config_from_dict
from src.rules.manager import RuleManager
from src.rules.repository import RuleRepository


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class TestCase:
    id: str
    text: str
    expected_risk: str  # "high" | "medium" | "low"
    expected_category: Optional[str] = None  # "sexual" | "violent" | ...
    note: str = ""
    bypass_types: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case: TestCase
    predicted_risk: str
    predicted_category: Optional[str]
    confidence: float
    is_correct_risk: bool
    is_correct_category: bool
    duration_ms: float
    evidence_count: int
    matched_patterns: list[str] = field(default_factory=list)


# =============================================================================
# Loader
# =============================================================================


def load_yaml_map(path: str) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(k): str(v) for k, v in (data or {}).items()}


def load_test_cases(cases_dir: str) -> list[TestCase]:
    """Load all YAML test case files from a directory."""
    cases: list[TestCase] = []
    dir_path = Path(cases_dir)
    if not dir_path.exists():
        print(f"Warning: {cases_dir} not found")
        return cases

    for yaml_file in sorted(dir_path.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        file_expected_risk = data.get("expected_risk", "high")
        file_expected_category = data.get("expected_category")

        for entry in data.get("cases", []):
            cases.append(
                TestCase(
                    id=entry.get("id", ""),
                    text=entry.get("text", ""),
                    expected_risk=entry.get("expected_risk", file_expected_risk),
                    expected_category=entry.get("expected_category", file_expected_category),
                    note=entry.get("note", ""),
                    bypass_types=entry.get("bypass_types", []),
                )
            )

    return cases


# =============================================================================
# Pipeline Runner
# =============================================================================


def build_normalizer() -> TextNormalizer:
    """Build TextNormalizer with all funNLP config maps loaded."""
    cfg = NormalizerConfig(
        bypass_map=load_yaml_map("config/bypass_variants.yaml"),
        confusable_map=load_yaml_map("config/confusable_chars.yaml"),
        pinyin_map=load_yaml_map("config/pinyin_variants.yaml"),
        traditional_simplified_map=load_yaml_map("config/traditional_simplified.yaml"),
        abbreviation_map=load_yaml_map("config/abbreviation_map.yaml"),
        decomposition_map=load_yaml_map("config/decomposition_map.yaml"),
    )
    return TextNormalizer(cfg)


def run_pipeline(
    case: TestCase,
    normalizer: TextNormalizer,
    rule_detector: RuleDetector,
    semantic_detector: SemanticDetector | None,
    fusion: RiskFusion,
) -> EvalResult:
    """Run one test case through the full pipeline."""
    t0 = time.perf_counter()

    # Step 1: Normalize
    normalized = normalizer.normalize(case.text)

    # Step 2: Rule detection
    rule_evidence = rule_detector.detect(normalized.normalized)

    # Step 3: Semantic detection (optional)
    semantic_evidence: list = []
    if semantic_detector is not None:
        semantic_evidence = semantic_detector.detect(normalized.normalized)

    # Step 4: Risk fusion
    risk_result = fusion.evaluate_input(rule_evidence, semantic_evidence)

    elapsed = (time.perf_counter() - t0) * 1000

    predicted_risk = risk_result.risk_level.value
    predicted_category = risk_result.risk_category.value if risk_result.risk_category else None
    is_correct_risk = predicted_risk == case.expected_risk
    is_correct_category = (
        predicted_category == case.expected_category
        if case.expected_category and predicted_category
        else (case.expected_category is None and predicted_category is None)
    )

    return EvalResult(
        case=case,
        predicted_risk=predicted_risk,
        predicted_category=predicted_category,
        confidence=risk_result.confidence,
        is_correct_risk=is_correct_risk,
        is_correct_category=is_correct_category,
        duration_ms=elapsed,
        evidence_count=len(risk_result.evidence_chain),
        matched_patterns=[e.matched_pattern for e in risk_result.evidence_chain],
    )


# =============================================================================
# Metrics
# =============================================================================


@dataclass
class Metrics:
    total: int
    correct_risk: int
    correct_category: int
    accuracy: float
    # Per-category
    per_category: dict[str, dict[str, float]]  # {cat: {precision, recall, f1, support}}
    # Binary (violation detection)
    true_positives: int  # violation → predicted violation
    false_positives: int  # normal → predicted violation
    true_negatives: int  # normal → predicted normal
    false_negatives: int  # violation → predicted normal
    fpr: float  # false positive rate
    fnr: float  # false negative rate
    # Timing
    avg_duration_ms: float
    # Details
    misclassified: list[EvalResult]  # false positives + false negatives
    per_bypass_type: dict[str, dict[str, float]]  # {bypass_type: {correct, total, rate}}


def compute_metrics(results: list[EvalResult]) -> Metrics:
    """Compute all evaluation metrics from pipeline results."""
    total = len(results)
    correct_risk = sum(1 for r in results if r.is_correct_risk)
    correct_category = sum(1 for r in results if r.is_correct_category)

    accuracy = correct_risk / total if total > 0 else 0.0
    avg_ms = sum(r.duration_ms for r in results) / total if total > 0 else 0.0

    # Per-category metrics
    categories = {"sexual", "violent", "advertising", "sensitive", "normal"}
    per_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for r in results:
        expected_cat = r.case.expected_category or "normal"
        predicted_cat = r.predicted_category or "normal"

        # For each category: is this case expected to be in it?
        for cat in categories:
            exp_in_cat = expected_cat == cat
            pred_in_cat = predicted_cat == cat

            if exp_in_cat and pred_in_cat:
                per_cat[cat]["tp"] += 1
            elif not exp_in_cat and pred_in_cat:
                per_cat[cat]["fp"] += 1
            elif exp_in_cat and not pred_in_cat:
                per_cat[cat]["fn"] += 1

    per_category: dict[str, dict[str, float]] = {}
    for cat in sorted(categories):
        tp = per_cat[cat]["tp"]
        fp = per_cat[cat]["fp"]
        fn = per_cat[cat]["fn"]
        support = tp + fn  # total expected in this category

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_category[cat] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    # Binary metrics (violation detection)
    tp = 0  # violation → predicted violation
    fp = 0  # normal → predicted violation
    tn = 0  # normal → predicted normal
    fn = 0  # violation → predicted normal

    for r in results:
        exp_is_safe = r.case.expected_risk == "low"
        pred_is_safe = r.predicted_risk == "low"

        if exp_is_safe and pred_is_safe:
            tn += 1
        elif exp_is_safe and not pred_is_safe:
            fp += 1
        elif not exp_is_safe and pred_is_safe:
            fn += 1
        else:
            tp += 1

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0  # false positive rate
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0  # false negative rate

    # Misclassified
    misclassified = [r for r in results if not r.is_correct_risk]

    # Per-bypass-type metrics
    bypass_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in results:
        for bt in r.case.bypass_types:
            bypass_stats[bt]["total"] += 1
            if r.is_correct_risk:
                bypass_stats[bt]["correct"] += 1

    per_bypass_type: dict[str, dict[str, float]] = {}
    for bt, stats in sorted(bypass_stats.items()):
        per_bypass_type[bt] = {
            "correct": stats["correct"],
            "total": stats["total"],
            "rate": round(stats["correct"] / stats["total"], 4) if stats["total"] > 0 else 0.0,
        }

    return Metrics(
        total=total,
        correct_risk=correct_risk,
        correct_category=correct_category,
        accuracy=round(accuracy, 4),
        per_category=per_category,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        fpr=round(fpr, 4),
        fnr=round(fnr, 4),
        avg_duration_ms=round(avg_ms, 2),
        misclassified=misclassified,
        per_bypass_type=per_bypass_type,
    )


# =============================================================================
# Reporters
# =============================================================================


def report_console(metrics: Metrics) -> str:
    """Generate a human-readable console report."""
    lines = []
    sep = "=" * 72

    lines.append(sep)
    lines.append("  内容风控系统 — 量化评估报告")
    lines.append(sep)
    lines.append(f"  测试用例总数: {metrics.total}")
    lines.append(
        f"  风险等级准确率: {metrics.accuracy:.1%} ({metrics.correct_risk}/{metrics.total})"
    )
    lines.append(f"  类别分类准确率: {metrics.correct_category}/{metrics.total}")
    lines.append(f"  平均处理时间: {metrics.avg_duration_ms:.2f} ms")
    lines.append("")

    # Binary metrics
    lines.append("  违规检测 (Binary):")
    lines.append(f"    TP={metrics.true_positives}  FP={metrics.false_positives}")
    lines.append(f"    TN={metrics.true_negatives}  FN={metrics.false_negatives}")
    lines.append(f"    误报率 (FPR): {metrics.fpr:.1%}  — 正常文本被判为违规")
    lines.append(f"    漏报率 (FNR): {metrics.fnr:.1%}  — 违规文本被放行")
    lines.append("")

    # Per-category
    lines.append(f"  {'类别':<14} {'精确率':>8} {'召回率':>8} {'F1':>8} {'样本数':>6}")
    lines.append(f"  {'-' * 44}")
    for cat in ["normal", "sexual", "violent", "advertising", "sensitive"]:
        m = metrics.per_category.get(cat, {})
        lines.append(
            f"  {cat:<14} {m.get('precision', 0):>8.1%} "
            f"{m.get('recall', 0):>8.1%} {m.get('f1', 0):>8.1%} "
            f"{m.get('support', 0):>6}"
        )
    lines.append("")

    # Per-bypass-type
    if metrics.per_bypass_type:
        lines.append(f"  绕过类型检出率:")
        for bt, stats in metrics.per_bypass_type.items():
            lines.append(
                f"    {bt:<16} {stats['correct']:>3}/{stats['total']:<3} = {stats['rate']:.1%}"
            )
        lines.append("")

    # Misclassified details
    if metrics.misclassified:
        lines.append(f"  误判/漏报详情 ({len(metrics.misclassified)} 条):")
        lines.append(f"  {'ID':<18} {'期望':>6} {'预测':>6} {'文本'}")
        lines.append(f"  {'-' * 60}")
        for r in metrics.misclassified:
            text_preview = r.case.text[:32].replace("\n", " ")
            lines.append(
                f"  {r.case.id:<18} {r.case.expected_risk:>6} {r.predicted_risk:>6} {text_preview}"
            )
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def report_markdown(metrics: Metrics) -> str:
    """Generate a Markdown report."""
    lines = []
    lines.append("# 内容风控系统 量化评估报告")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 测试用例总数 | {metrics.total} |")
    lines.append(f"| 风险等级准确率 | {metrics.accuracy:.1%} |")
    lines.append(f"| 平均处理时间 | {metrics.avg_duration_ms:.2f} ms |")
    lines.append(f"| 误报率 (FPR) | {metrics.fpr:.1%} |")
    lines.append(f"| 漏报率 (FNR) | {metrics.fnr:.1%} |")
    lines.append("")

    lines.append("## 混淆矩阵 (Binary)")
    lines.append("")
    lines.append("| | 预测违规 | 预测正常 |")
    lines.append("|---|---|---|")
    lines.append(f"| 实际违规 | {metrics.true_positives} | {metrics.false_negatives} |")
    lines.append(f"| 实际正常 | {metrics.false_positives} | {metrics.true_negatives} |")
    lines.append("")

    lines.append("## 各类别指标")
    lines.append("")
    lines.append("| 类别 | 精确率 | 召回率 | F1 | 样本数 |")
    lines.append("|------|--------|--------|-----|--------|")
    for cat in ["normal", "sexual", "violent", "advertising", "sensitive"]:
        m = metrics.per_category.get(cat, {})
        lines.append(
            f"| {cat} | {m.get('precision', 0):.1%} | "
            f"{m.get('recall', 0):.1%} | {m.get('f1', 0):.1%} | "
            f"{m.get('support', 0)} |"
        )
    lines.append("")

    if metrics.misclassified:
        lines.append("## 误判/漏报详情")
        lines.append("")
        lines.append("| ID | 期望 | 预测 | 文本 |")
        lines.append("|----|------|------|------|")
        for r in metrics.misclassified:
            text_preview = r.case.text[:40].replace("\n", " ")
            lines.append(
                f"| {r.case.id} | {r.case.expected_risk} | {r.predicted_risk} | {text_preview} |"
            )
        lines.append("")

    return "\n".join(lines)


def report_json(metrics: Metrics) -> str:
    """Generate a JSON report."""
    data = {
        "total": metrics.total,
        "accuracy": metrics.accuracy,
        "fpr": metrics.fpr,
        "fnr": metrics.fnr,
        "avg_duration_ms": metrics.avg_duration_ms,
        "true_positives": metrics.true_positives,
        "false_positives": metrics.false_positives,
        "true_negatives": metrics.true_negatives,
        "false_negatives": metrics.false_negatives,
        "per_category": metrics.per_category,
        "per_bypass_type": metrics.per_bypass_type,
        "misclassified": [
            {
                "id": r.case.id,
                "text": r.case.text,
                "expected_risk": r.case.expected_risk,
                "predicted_risk": r.predicted_risk,
                "expected_category": r.case.expected_category,
                "predicted_category": r.predicted_category,
                "confidence": r.confidence,
                "note": r.case.note,
                "bypass_types": r.case.bypass_types,
            }
            for r in metrics.misclassified
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate content filtering pipeline")
    parser.add_argument(
        "--cases-dir",
        default="data/test_cases",
        help="Directory containing test case YAML files (default: data/test_cases)",
    )
    parser.add_argument(
        "--output",
        choices=["console", "markdown", "json"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip semantic model loading (rules-only evaluation, faster)",
    )
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="风险策略配置文件（默认: config/default.yaml）",
    )
    parser.add_argument(
        "--rules-dir",
        default="config/rules",
        help="Rules directory (default: config/rules)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show per-case results even when correct",
    )
    args = parser.parse_args()

    # Load test cases
    cases = load_test_cases(args.cases_dir)
    if not cases:
        print("No test cases found. Create YAML files in data/test_cases/")
        sys.exit(1)
    print(f"Loaded {len(cases)} test cases from {args.cases_dir}")

    # Initialize pipeline
    print("Initializing pipeline...")
    normalizer = build_normalizer()

    with open(args.config, "r", encoding="utf-8") as f:
        app_config = yaml.safe_load(f) or {}
    fusion_config = fusion_config_from_dict(app_config.get("risk_fusion", {}))

    repo = RuleRepository(args.rules_dir)
    manager = RuleManager(repo)
    rule_detector = RuleDetector(manager, level_confidence=fusion_config.rule_confidence)

    semantic_detector: SemanticDetector | None = None
    if not args.no_semantic:
        try:
            semantic_detector = SemanticDetector(
                model_name="BAAI/bge-small-zh-v1.5",
                confidence_threshold=0.6,
                device="cpu",
            )
            semantic_detector.load_model()
            print("  Semantic model loaded")
        except Exception as e:
            print(f"  Semantic model unavailable: {e}")
            print("  Falling back to rules-only mode")

    fusion = RiskFusion(fusion_config)

    # Run evaluation
    print(f"Running evaluation on {len(cases)} cases...")
    results: list[EvalResult] = []
    for case in cases:
        result = run_pipeline(case, normalizer, rule_detector, semantic_detector, fusion)
        results.append(result)

        if args.detail or not result.is_correct_risk:
            status = "OK" if result.is_correct_risk else "MISMATCH"
            print(
                f"  [{status}] {case.id}: "
                f"expected={case.expected_risk}/{case.expected_category} "
                f"predicted={result.predicted_risk}/{result.predicted_category} "
                f"conf={result.confidence:.2f}"
            )

    # Compute metrics
    metrics = compute_metrics(results)

    # Report
    if args.output == "markdown":
        print(report_markdown(metrics))
    elif args.output == "json":
        print(report_json(metrics))
    else:
        print(report_console(metrics))

    # Exit code: 1 if any misclassified, 0 otherwise
    if metrics.misclassified:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
