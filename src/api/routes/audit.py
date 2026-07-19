"""审计日志端点。"""

import json
from datetime import datetime

from fastapi import APIRouter, Query

from src.api.bootstrap import AppComponents

router = APIRouter()


@router.get("/api/audit")
def list_audit_logs(limit: int = Query(default=50, description="返回条数上限")):
    """获取最近的审计日志条目。

    Args:
        limit: 返回的最大记录数，默认 50。

    Returns:
        审计记录列表，按时间倒序排列。
    """
    components = AppComponents.get()
    _audit_logger = components.audit_logger

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = _audit_logger.log_dir / f"audit-{today}.jsonl"
    records: list[dict] = []

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    inp = entry.get("input", {})
                    out = entry.get("output", {})
                    perf = entry.get("performance", {})
                    llm = entry.get("llm", {})
                    records.append(
                        {
                            "requestId": entry.get("request_id", ""),
                            "timestamp": entry.get("timestamp", ""),
                            "action": inp.get("action", "pass"),
                            "riskLevel": inp.get("risk_level", "low"),
                            "category": inp.get("risk_category"),
                            "evidenceCount": inp.get("evidence_count", 0),
                            "llmCalled": llm.get("called", False),
                            "outputBlocked": out.get("blocked", False),
                            "durationMs": perf.get("total_duration_ms", 0),
                        }
                    )
                except json.JSONDecodeError:
                    continue

    # 返回最新的记录，按 limit 截取
    records.reverse()
    return records[:limit]
