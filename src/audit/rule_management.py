"""规则管理审计 — 记录规则启用/禁用和重载操作的审计轨迹。

写入独立的 JSONL 日志文件，用于追溯规则变更历史。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path


class RuleManagementAuditLogger:
    """记录规则管理操作的审计日志。

    记录两类事件：
    - 规则启用状态变更（谁在何时启用了/禁用了哪条规则）
    - 规则重载操作（重载前后的版本号和规则数量）
    """

    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_enabled_change(
        self,
        rule_id: str,
        category: str,
        source: str,
        previous_enabled: bool,
        new_enabled: bool,
        version_before: str,
        version_after: str,
    ) -> None:
        """追加一条成功的显式启用状态变更事件。"""
        self._append(
            {
                "action": "rule_enabled_changed",
                "rule_id": rule_id,
                "category": category,
                "source": source,
                "previous_enabled": previous_enabled,
                "new_enabled": new_enabled,
                "version_before": version_before,
                "version_after": version_after,
            }
        )

    def log_reload(
        self,
        version_before: str,
        version_after: str,
        total: int,
        enabled_total: int,
    ) -> None:
        """追加一条成功的规则集重载事件。"""
        self._append(
            {
                "action": "rules_reloaded",
                "version_before": version_before,
                "version_after": version_after,
                "total": total,
                "enabled_total": enabled_total,
            }
        )

    def _append(self, event: dict) -> None:
        """写入一条事件记录（不包含凭据或请求头数据）。"""
        timestamp = datetime.now().isoformat()
        payload = {"event_id": str(uuid.uuid4()), "timestamp": timestamp, **event}
        path = self.log_dir / f"rule-management-{timestamp[:10]}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
