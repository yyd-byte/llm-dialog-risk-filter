"""Audit logging — records every request with structured JSONL output."""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.decision.models import RiskLevel, RiskCategory


@dataclass
class AuditRecord:
    """A single audit log entry for one request pipeline run."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    # Input side
    original_input: str = ""
    normalized_input: str = ""
    input_risk_level: str = RiskLevel.LOW.value
    input_risk_category: Optional[str] = None
    input_confidence: float = 0.0
    input_action: str = "pass"  # block | desensitize | pass
    input_evidence: list[dict] = field(default_factory=list)
    # Desensitization
    desensitized_input: str = ""
    # LLM call
    llm_called: bool = False
    llm_model: str = ""
    # Output side
    llm_output: str = ""
    output_risk_level: str = RiskLevel.LOW.value
    output_passed: bool = True
    output_blocked: bool = False
    # Final
    final_output: str = ""
    total_duration_ms: float = 0.0


class AuditLogger:
    """Writes structured audit records to JSONL files."""

    def __init__(self, log_dir: str = "data/logs",
                 max_file_size_mb: int = 10,
                 backup_count: int = 5):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.backup_count = backup_count

    def log(self, record: AuditRecord) -> None:
        """Write a single audit record to the log file."""
        self._rotate_if_needed()
        log_file = self._current_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._record_to_dict(record), ensure_ascii=False) + "\n")

    def _current_log_file(self) -> Path:
        """Get the current active log file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{today}.jsonl"

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        log_file = self._current_log_file()
        if log_file.exists() and log_file.stat().st_size > self.max_file_size:
            # Simple rotation: rename old file with timestamp
            ts = datetime.now().strftime("%H%M%S")
            rotated = log_file.with_suffix(f".{ts}.jsonl")
            log_file.rename(rotated)
            # Cleanup old backups
            self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Remove log files exceeding backup count."""
        log_files = sorted(self.log_dir.glob("audit-*.jsonl"), reverse=True)
        for f in log_files[self.backup_count:]:
            f.unlink()

    def _record_to_dict(self, r: AuditRecord) -> dict:
        """Convert AuditRecord to serializable dict."""
        return {
            "request_id": r.request_id,
            "timestamp": r.timestamp,
            "input": {
                "original": "[REDACTED]",  # Privacy: don't store raw text in logs
                "normalized_length": len(r.normalized_input),
                "risk_level": r.input_risk_level,
                "risk_category": r.input_risk_category,
                "confidence": r.input_confidence,
                "action": r.input_action,
                "evidence_count": len(r.input_evidence),
            },
            "llm": {
                "called": r.llm_called,
                "model": r.llm_model,
            },
            "output": {
                "risk_level": r.output_risk_level,
                "passed": r.output_passed,
                "blocked": r.output_blocked,
            },
            "performance": {
                "total_duration_ms": r.total_duration_ms,
            },
        }