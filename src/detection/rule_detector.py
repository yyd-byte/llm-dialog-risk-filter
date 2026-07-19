"""基于规则的检测引擎 — 关键词和正则匹配。"""

import logging
import re
from threading import RLock

from src.decision.models import DetectionSource, Evidence, RiskLevel
from src.detection.keyword_automaton import KeywordAutomaton
from src.rules.manager import RuleManager
from src.rules.models import Rule

logger = logging.getLogger(__name__)


class RuleDetector:
    """快速规则检测，同时支持关键词（AC 自动机）和正则表达式。

    检测流程：
    1. AC 自动机扫描全部关键词（单次遍历，O(n)）
    2. 逐条正则编译匹配
    3. 按声明顺序收集证据，每条规则最多产生一条证据

    线程安全：通过 RLock 保护缓存替换操作。
    """

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
        """构建新缓存并原子化发布。"""
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
        """从管理器的当前内存快照重建匹配器缓存。"""
        self._rebuild_cache()

    def reload(self) -> None:
        """从管理器重新加载规则，重建所有匹配器缓存。"""
        self._rule_manager.reload()
        self._rebuild_cache()

    def detect(self, text: str) -> list[Evidence]:
        """对规范化文本执行规则检测。

        按规则声明顺序返回 Evidence 列表，每条命中规则对应一条证据。
        同一规则在文本中多次出现只记录一次。

        Args:
            text: 规范化后的输入文本。

        Returns:
            命中规则的 Evidence 列表；无命中时返回空列表。
        """
        text_lower = text.lower()
        regex_matches: dict[int, str] = {}

        # 获取线程安全的缓存快照
        with self._lock:
            ordered_rules = self._ordered_rules
            compiled_regex = self._compiled_regex
            keyword_automaton = self._keyword_automaton
            empty_ordinals = self._empty_keyword_ordinals
            level_confidence = self._level_confidence

        # 第一步：AC 自动机扫描全部关键词（一次遍历）
        matched_ordinals = keyword_automaton.search(text_lower)
        matched_ordinals.update(empty_ordinals)

        # 第二步：逐条正则匹配
        for ordinal, compiled in compiled_regex.items():
            match_result = compiled.search(text_lower)
            if match_result:
                matched_ordinals.add(ordinal)
                regex_matches[ordinal] = match_result.group()

        # 第三步：按声明顺序收集证据
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
