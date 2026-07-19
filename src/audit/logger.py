"""审计日志 — 以结构化 JSONL 格式记录每次请求的处理全链路。"""

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
    """单次请求流水线运行的审计日志条目。"""

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
    """将结构化审计记录写入 JSONL 日志文件。

    特性：
    - 按天滚动的日志文件（audit-YYYY-MM-DD.jsonl）
    - 超大小自动轮转
    - 原始文本哈希化存储以保护隐私
    """

    def __init__(self, log_dir: str = "data/logs",
                 max_file_size_mb: int = 10,
                 backup_count: int = 5):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.backup_count = backup_count

    def log(self, record: AuditRecord) -> None:
        """将单条审计记录写入日志文件。"""
        self._rotate_if_needed()
        log_file = self._current_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._record_to_dict(record), ensure_ascii=False) + "\n")

    def _current_log_file(self) -> Path:
        """获取当前日期的活动日志文件路径。

        Returns:
            形如 data/logs/audit-2026-07-20.jsonl 的 Path 对象。
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{today}.jsonl"

    def _rotate_if_needed(self) -> None:
        """当日志文件超出大小时轮转。"""
        log_file = self._current_log_file()
        if log_file.exists() and log_file.stat().st_size > self.max_file_size:
            # 简单轮转：用时间戳重命名旧文件
            ts = datetime.now().strftime("%H%M%S")
            rotated = log_file.with_suffix(f".{ts}.jsonl")
            log_file.rename(rotated)
            # Cleanup old backups
            self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """删除超出备份数量上限的旧日志文件。"""
        log_files = sorted(self.log_dir.glob("audit-*.jsonl"), reverse=True)
        for f in log_files[self.backup_count:]:
            f.unlink()

    def _record_to_dict(self, r: AuditRecord) -> dict:
        """将 AuditRecord 转换为可序列化的字典。

        存储完整的证据链以便审计追溯。
        原始输入文本经哈希处理以保护隐私；完整文本可在需要审计时从安全存储恢复。
        """
        import hashlib
        text_hash = hashlib.sha256(
            r.original_input.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        return {
            "request_id": r.request_id,
            "timestamp": r.timestamp,
            "input": {
                "original_hash": text_hash,
                "original_length": len(r.original_input),
                "normalized_length": len(r.normalized_input),
                "risk_level": r.input_risk_level,
                "risk_category": r.input_risk_category,
                "confidence": r.input_confidence,
                "action": r.input_action,
                "evidence": [
                    {
                        "step": ev.get("step", ""),
                        "source": ev.get("source", ""),
                        "category": ev.get("category", ""),
                        "confidence": ev.get("confidence", 0.0),
                        "explanation": ev.get("explanation", ""),
                    }
                    for ev in r.input_evidence
                ],
            },
            "desensitization": {
                "desensitized": r.desensitized_input != "",
                "desensitized_length": len(r.desensitized_input),
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