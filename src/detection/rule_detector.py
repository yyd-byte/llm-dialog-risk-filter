"""Rule-based detection engine — keyword and regex matching."""

import re
from typing import Optional

from src.decision.models import DetectionSource, Evidence, RiskLevel
from src.detection.keyword_automaton import KeywordAutomaton
from src.rules.manager import RuleManager
from src.rules.models import Rule


class RuleDetector:
    """Fast rule-based detection using keyword and regex patterns."""

    DEFAULT_LEVEL_CONFIDENCE = {
        RiskLevel.LOW: 0.2,
        RiskLevel.MEDIUM: 0.58,
        RiskLevel.HIGH: 1.0,
    }

    def __init__(
        self,
        rule_manager: RuleManager,
        level_confidence: dict[RiskLevel, float] | None = None,
    ):
        self._rule_manager = rule_manager
        self._level_confidence = {
            **self.DEFAULT_LEVEL_CONFIDENCE,
            **(level_confidence or {}),
        }
        self._ordered_rules: list[Rule] = []
        self._compiled_regex: dict[int, re.Pattern] = {}
        self._keyword_automaton = KeywordAutomaton([])
        self._empty_keyword_ordinals: set[int] = set()
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        """Rebuild enabled-rule snapshots, keyword automaton, and regex cache."""
        self._ordered_rules = self._rule_manager.get_enabled_rules()
        self._compiled_regex.clear()
        keyword_patterns: list[tuple[str, int]] = []
        self._empty_keyword_ordinals.clear()

        for ordinal, rule in enumerate(self._ordered_rules):
            if rule.pattern_type == "keyword":
                pattern = rule.pattern.lower()
                if pattern:
                    keyword_patterns.append((pattern, ordinal))
                else:
                    self._empty_keyword_ordinals.add(ordinal)
            elif rule.pattern_type == "regex":
                try:
                    self._compiled_regex[ordinal] = re.compile(rule.pattern, re.IGNORECASE)
                except re.error:
                    pass

        self._keyword_automaton = KeywordAutomaton(keyword_patterns)

    def rebuild_cache(self) -> None:
        """Rebuild matcher caches from the manager's current in-memory snapshot."""
        self._rebuild_cache()

    def reload(self) -> None:
        """Reload rules from manager and rebuild all matcher caches."""
        self._rule_manager.reload()
        self._rebuild_cache()

    def detect(self, text: str) -> list[Evidence]:
        """Run rule-based detection on normalized text.

        Returns one evidence item for each matching rule in the original rule
        declaration order. Repeated occurrences of one rule emit once.
        """
        text_lower = text.lower()
        matched_ordinals = self._keyword_automaton.search(text_lower)
        matched_ordinals.update(self._empty_keyword_ordinals)
        regex_matches: dict[int, str] = {}

        for ordinal, compiled in self._compiled_regex.items():
            match = compiled.search(text_lower)
            if match:
                matched_ordinals.add(ordinal)
                regex_matches[ordinal] = match.group()

        evidence_list: list[Evidence] = []
        for ordinal in sorted(matched_ordinals):
            rule = self._ordered_rules[ordinal]
            match_result = regex_matches.get(ordinal, rule.pattern)
            evidence_list.append(
                Evidence(
                    source=DetectionSource.RULE,
                    category=rule.category,
                    confidence=self._level_confidence[rule.risk_level],
                    matched_pattern=rule.pattern,
                    matched_text=match_result,
                    explanation=f"命中规则: {rule.description or rule.id}",
                    step="rule",
                    declared_risk_level=rule.risk_level,
                    metadata={"rule_id": rule.id},
                )
            )
        return evidence_list

    def _match_rule(self, rule: Rule, text: str) -> Optional[str]:
        """Retain single-rule matching semantics for callers and compatibility tests."""
        if rule.pattern_type == "keyword":
            return rule.pattern if rule.pattern.lower() in text else None
        if rule.pattern_type == "regex":
            for ordinal, cached_rule in enumerate(self._ordered_rules):
                if cached_rule is rule:
                    compiled = self._compiled_regex.get(ordinal)
                    if compiled:
                        match = compiled.search(text)
                        return match.group() if match else None
        return None
