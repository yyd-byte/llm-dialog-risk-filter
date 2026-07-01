"""End-to-end pipeline integration tests."""

import pytest
from src.detection.normalizer import TextNormalizer
from src.decision.models import RiskLevel


class TestPipeline:
    """Integration tests for the full pipeline."""

    def test_normal_text_full_pipeline(self, normalizer, rule_detector,
                                       semantic_detector, fusion,
                                       desensitizer, output_checker,
                                       audit_logger):
        """Normal text should pass through the entire pipeline."""
        text = "今天天气真好，适合出去散步"

        # Step 1: Normalize
        norm = normalizer.normalize(text)

        # Step 2: Rule detection
        rule_ev = rule_detector.detect(norm.normalized)

        # Step 3: Semantic
        sem_ev = semantic_detector.detect(norm.normalized)

        # Step 4: Fusion
        risk = fusion.evaluate(rule_ev, sem_ev)

        # Normal text should be LOW risk
        assert risk.risk_level == RiskLevel.LOW
        assert risk.is_safe is True

        # Step 5: Output check
        llm_output = "这是大模型的正常回复"
        out = output_checker.check(llm_output)
        assert out.is_safe is True

        # Step 6: Audit log
        from src.audit.logger import AuditRecord
        record = AuditRecord(
            original_input=text,
            normalized_input=norm.normalized,
            input_risk_level=risk.risk_level.value,
            input_action=risk.action,
            llm_output=llm_output,
            output_passed=out.is_safe,
            final_output=out.final_output,
        )
        audit_logger.log(record)  # Should not raise

    def test_risk_text_pipeline(self, normalizer, rule_detector,
                                semantic_detector, fusion, output_checker,
                                audit_logger):
        """Risk text should be detected by the pipeline."""
        text = "违规词测试内容"

        norm = normalizer.normalize(text)
        rule_ev = rule_detector.detect(norm.normalized)
        sem_ev = semantic_detector.detect(norm.normalized)
        risk = fusion.evaluate(rule_ev, sem_ev)

        # Risk text should be detected
        assert risk.risk_level != RiskLevel.LOW
        assert len(risk.evidence_chain) > 0

    def test_audit_log_written(self, normalizer, rule_detector,
                               semantic_detector, fusion, output_checker,
                               audit_logger):
        """Audit log should be written to file."""
        from src.audit.logger import AuditRecord
        import json
        from pathlib import Path

        record = AuditRecord(
            original_input="test",
            input_risk_level="low",
            input_action="pass",
        )
        audit_logger.log(record)

        # Check that log file exists and contains the record
        log_files = list(audit_logger.log_dir.glob("audit-*.jsonl"))
        assert len(log_files) > 0

        with open(log_files[0], "r", encoding="utf-8") as f:
            content = f.read()
            assert "test" not in content  # Original text should be redacted
            assert "request_id" in content