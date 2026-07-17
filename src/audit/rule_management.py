"""Append-only audit logging for successful rule-management operations."""

import json
import uuid
from datetime import datetime
from pathlib import Path


class RuleManagementAuditLogger:
    """Write privacy-safe rule-management events to daily JSONL files."""

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
        """Append one successful explicit enabled-state change event."""
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
        """Append one successful ruleset reload event."""
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
        """Write one event without credentials or request-header data."""
        timestamp = datetime.now().isoformat()
        payload = {"event_id": str(uuid.uuid4()), "timestamp": timestamp, **event}
        path = self.log_dir / f"rule-management-{timestamp[:10]}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
