"""Rule-based detection engine — keyword and regex matching."""

import re
from typing import Optional

from src.rules.models import Rule, RuleMatch
from src.rules.manager import RuleManager
from src.decision.models import Evidence, DetectionSource, RiskCategory, RiskLevel


class RuleDetector:
    """Fast rule-based detection using keyword and regex patterns.

    This is the first layer of the dual-filter architecture, responsible
    for "fast recall" of obvious violations.
    """

    def __init__(self, rule_manager: RuleManager):
        self._rule_manager = rule_manager
        # Pre-compile regex patterns for performance
        self._compiled_regex: dict[str, re.Pattern] = {}
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        """Rebuild compiled regex cache from enabled rules."""
        self._compiled_regex.clear()
        for rule in self._rule_manager.get_enabled_rules():
            if rule.pattern_type == "regex":
                try:
                    self._compiled_regex[rule.id] = re.compile(
                        rule.pattern, re.IGNORECASE
                    )
                except re.error:
                    pass  # Skip invalid regex

    def reload(self) -> None:
        """Reload rules from manager and rebuild cache."""
        self._rule_manager.reload()
        self._rebuild_cache()

    def detect(self, text: str) -> list[Evidence]:
        """Run rule-based detection on normalized text.

        Returns a list of Evidence objects, one per matched rule.
        """
        evidence_list: list[Evidence] = []
        text_lower = text.lower()

        for rule in self._rule_manager.get_enabled_rules():
            if not rule.enabled:
                continue

            match_result = self._match_rule(rule, text_lower)
            if match_result is not None:
                evidence_list.append(Evidence(
                    source=DetectionSource.RULE,
                    category=rule.category,
                    confidence=1.0 if rule.risk_level == RiskLevel.HIGH else 0.7,
                    matched_pattern=rule.pattern,
                    matched_text=match_result,
                    explanation=f"命中规则: {rule.description or rule.id}",
                ))

        return evidence_list

    def _match_rule(self, rule: Rule, text: str) -> Optional[str]:
        """Try to match a single rule against text. Returns matched text or None."""
        if rule.pattern_type == "keyword":
            if rule.pattern.lower() in text:
                return rule.pattern
        elif rule.pattern_type == "regex":
            compiled = self._compiled_regex.get(rule.id)
            if compiled:
                m = compiled.search(text)
                if m:
                    return m.group()
        return None