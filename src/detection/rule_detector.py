"""Rule-based detection engine — keyword and regex matching."""

import logging
import re
from threading import RLock

from src.decision.models import DetectionSource, Evidence, RiskLevel
from src.detection.keyword_automaton import KeywordAutomaton
from src.rules.manager import RuleManager
from src.rules.models import Rule

logger = logging.getLogger(__name__)


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
        self._lock = RLock()
        self._ordered_rules: list[Rule] = []
        self._compiled_regex: dict[int, re.Pattern] = {}
        self._keyword_automaton = KeywordAutomaton([])
        self._empty_keyword_ordinals: set[int] = set()
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        """Build new caches and atomically publish them."""
        ordered = self._rule_manager.get_enabled_rules()
        compiled: dict[int, re.Pattern] = {}
        keyword_patterns: list[tuple[str, int]] = []
        empty_ordinals: set[int] = set()

        for ordinal, rule in enumerate(ordered):
            if rule.pattern_type == "keyword":
                pattern = rule.pattern.lower()
                if pattern:
                    keyword_patterns.append((pattern, ordinal))
                else:
                    empty_ordinals.add(ordinal)
            elif rule.pattern_type == "regex":
                try:
                    compiled[ordinal] = re.compile(rule.pattern, re.IGNORECASE)
                except re.error:
                    logger.warning("跳过无效正则规则 %s: %r", rule.id, rule.pattern)

        automaton = KeywordAutomaton(keyword_patterns)

        with self._lock:
            self._ordered_rules = ordered
            self._compiled_regex = compiled
            self._keyword_automaton = automaton
            self._empty_keyword_ordinals = empty_ordinals

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
        regex_matches: dict[int, str] = {}

        with self._lock:
            ordered_rules = self._ordered_rules
            compiled_regex = self._compiled_regex
            keyword_automaton = self._keyword_automaton
            empty_ordinals = self._empty_keyword_ordinals
            level_confidence = self._level_confidence

        matched_ordinals = keyword_automaton.search(text_lower)
        matched_ordinals.update(empty_ordinals)

        for ordinal, compiled in compiled_regex.items():
            match_result = compiled.search(text_lower)
            if match_result:
                matched_ordinals.add(ordinal)
                regex_matches[ordinal] = match_result.group()

        evidence_list: list[Evidence] = []
        for ordinal in sorted(matched_ordinals):
            rule = ordered_rules[ordinal]
            evidence_list.append(
                Evidence(
                    source=DetectionSource.RULE,
                    category=rule.category,
                    confidence=level_confidence[rule.risk_level],
                    matched_pattern=rule.pattern,
                    matched_text=regex_matches.get(ordinal, rule.pattern),
                    explanation=f"命中规则: {rule.description or rule.id}",
                    step="rule",
                    declared_risk_level=rule.risk_level,
                    metadata={"rule_id": rule.id},
                )
            )
        return evidence_list
