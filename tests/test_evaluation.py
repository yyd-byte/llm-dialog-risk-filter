"""Tests for the evaluation system itself."""

import json
from pathlib import Path

import pytest

# Import evaluation components
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.evaluate import (
    TestCase,
    EvalResult,
    Metrics,
    compute_metrics,
    load_test_cases,
    report_json,
    report_markdown,
    report_console,
)


class TestLoadTestCases:
    """Test case loading from YAML files."""

    def test_load_all_cases(self):
        """Should load test cases from all YAML files."""
        cases = load_test_cases("data/test_cases")
        assert len(cases) >= 50, f"Expected 50+ cases, got {len(cases)}"

    def test_normal_cases_exist(self):
        """Normal text cases should all expect LOW risk."""
        cases = load_test_cases("data/test_cases")
        normal = [c for c in cases if c.expected_risk == "low"]
        assert len(normal) >= 10, f"Expected 10+ normal cases, got {len(normal)}"

    def test_violation_cases_exist(self):
        """Violation cases should span all 4 categories."""
        cases = load_test_cases("data/test_cases")
        cats = set()
        for c in cases:
            if c.expected_category:
                cats.add(c.expected_category)
        assert "sexual" in cats
        assert "violent" in cats
        assert "advertising" in cats
        assert "sensitive" in cats

    def test_evasion_cases_have_bypass_types(self):
        """Evasion cases should have bypass_types annotated."""
        cases = load_test_cases("data/test_cases")
        evasion = [c for c in cases if c.bypass_types]
        assert len(evasion) >= 15, f"Expected 15+ evasion cases, got {len(evasion)}"
        # Check that major bypass types are covered
        all_types = set()
        for c in evasion:
            all_types.update(c.bypass_types)
        assert "homophone" in all_types, "Missing homophone bypass tests"
        assert "decomposition" in all_types, "Missing decomposition bypass tests"
        assert "separator" in all_types, "Missing separator bypass tests"


class TestComputeMetrics:
    """Test metric computation."""

    def _make_result(
        self,
        case_id: str,
        text: str,
        expected_risk: str,
        predicted_risk: str,
        expected_cat: str | None = None,
        predicted_cat: str | None = None,
    ) -> EvalResult:
        return EvalResult(
            case=TestCase(
                id=case_id, text=text, expected_risk=expected_risk, expected_category=expected_cat
            ),
            predicted_risk=predicted_risk,
            predicted_category=predicted_cat,
            confidence=0.8,
            is_correct_risk=expected_risk == predicted_risk,
            is_correct_category=expected_cat == predicted_cat,
            duration_ms=5.0,
            evidence_count=1,
        )

    def test_perfect_accuracy(self):
        """All correct predictions should yield 1.0 accuracy."""
        results = [
            self._make_result("n1", "hello", "low", "low", None, None),
            self._make_result("s1", "bad", "high", "high", "sexual", "sexual"),
        ]
        m = compute_metrics(results)
        assert m.accuracy == 1.0
        assert m.fpr == 0.0
        assert m.fnr == 0.0

    def test_false_positive(self):
        """Normal text flagged as violation should count as FP."""
        results = [
            self._make_result("n1", "hello", "low", "high", None, "sexual"),
            self._make_result("v1", "bad", "high", "high", "sexual", "sexual"),
        ]
        m = compute_metrics(results)
        assert m.false_positives == 1
        assert m.fpr == 1.0
        assert m.accuracy == 0.5

    def test_false_negative(self):
        """Violation missed should count as FN."""
        results = [
            self._make_result("v1", "bad", "high", "low", "sexual", None),
            self._make_result("n1", "hello", "low", "low", None, None),
        ]
        m = compute_metrics(results)
        assert m.false_negatives == 1
        assert m.fnr == 1.0

    def test_per_category_metrics(self):
        """Each category should have precision/recall/f1 computed."""
        results = [
            self._make_result("s1", "sexual text", "high", "high", "sexual", "sexual"),
            self._make_result("s2", "sexual text 2", "high", "high", "sexual", "sexual"),
            self._make_result("f1", "false alarm", "low", "high", None, "sexual"),
        ]
        m = compute_metrics(results)
        sex = m.per_category.get("sexual", {})
        assert sex["precision"] == pytest.approx(0.6667, abs=0.001)  # 2 TP, 1 FP
        assert sex["recall"] == 1.0  # 2 TP, 0 FN

    def test_empty_results(self):
        """Empty results should not crash."""
        m = compute_metrics([])
        assert m.total == 0
        assert m.accuracy == 0.0

    def test_misclassified_list(self):
        """Misclassified results should be collected."""
        results = [
            self._make_result("n1", "normal", "low", "high", None, "sexual"),
            self._make_result("v1", "violation", "high", "high", "sexual", "sexual"),
        ]
        m = compute_metrics(results)
        assert len(m.misclassified) == 1
        assert m.misclassified[0].case.id == "n1"


class TestReporters:
    """Test report generation."""

    def _sample_metrics(self) -> Metrics:
        return Metrics(
            total=10,
            correct_risk=8,
            correct_category=7,
            accuracy=0.8,
            per_category={},
            true_positives=7,
            false_positives=1,
            true_negatives=1,
            false_negatives=1,
            fpr=0.5,
            fnr=0.125,
            avg_duration_ms=12.5,
            misclassified=[],
            per_bypass_type={},
        )

    def test_json_report_is_valid(self):
        """JSON report should be parseable."""
        m = self._sample_metrics()
        j = report_json(m)
        data = json.loads(j)
        assert data["total"] == 10
        assert data["accuracy"] == 0.8

    def test_markdown_report_has_headers(self):
        """Markdown report should contain expected sections."""
        m = self._sample_metrics()
        md = report_markdown(m)
        assert "# 内容风控系统" in md
        assert "混淆矩阵" in md
        assert "各类别指标" in md

    def test_console_report_has_sections(self):
        """Console report should contain key metrics."""
        m = self._sample_metrics()
        c = report_console(m)
        assert "量化评估报告" in c
        assert "80.0%" in c
        assert "误报率" in c
        assert "漏报率" in c
