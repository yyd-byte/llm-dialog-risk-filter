"""规则管理 — 查询、持久化及启用状态操作。

采用乐观锁版本控制，确保并发规则变更的安全性。
"""

from datetime import datetime
from threading import RLock

from src.decision.models import RiskCategory, RiskLevel
from src.rules.models import Rule, RuleCategoryMeta
from src.rules.repository import RuleRepository


class RuleVersionConflictError(Exception):
    """规则变更操作的目标版本与当前版本不一致时抛出。

    调用方应获取最新版本后重试。
    """


class RuleManager:
    """管理一份以 YAML 文件为后端的规则内存快照。

    提供规则的增删查改、启用/禁用、分页过滤及批量导入导出功能。
    所有写操作通过乐观锁（expected_version）防止并发冲突。
    """

    def __init__(self, repository: RuleRepository):
        self._repo = repository
        self._lock = RLock()
        self._rules: dict[RiskCategory, list[Rule]] = {}
        self.reload()

    def reload(self) -> None:
        """仅在全部文件加载成功后替换当前内存快照。"""
        candidate = self._repo.load_all()
        with self._lock:
            self._rules = candidate

    def rebuild_version(self) -> str:
        """返回当前持久化规则的版本。"""
        return self._repo.version()

    def get_enabled_rules(self, category: RiskCategory | None = None) -> list[Rule]:
        """获取已启用的规则，可按类别筛选。"""
        with self._lock:
            if category:
                return [rule for rule in self._rules.get(category, []) if rule.enabled]
            return [rule for rules in self._rules.values() for rule in rules if rule.enabled]

    def get_all_rules(self, category: RiskCategory | None = None) -> list[Rule]:
        """获取全部规则，可按类别筛选。"""
        with self._lock:
            if category:
                return list(self._rules.get(category, []))
            return [rule for rules in self._rules.values() for rule in rules]

    def add_rule(self, rule: Rule) -> None:
        """向当前内存快照中添加一条规则。"""
        with self._lock:
            self._rules.setdefault(rule.category, []).append(rule)

    def get_rule_by_id(self, rule_id: str) -> Rule | None:
        """根据 ID 查找规则。"""
        with self._lock:
            for rules in self._rules.values():
                for rule in rules:
                    if rule.id == rule_id:
                        return rule
        return None

    def list_rules(
        self,
        category: RiskCategory | None = None,
        source: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Rule], int]:
        """返回稳定的过滤后规则分页及总数。"""
        rules = self.get_all_rules(category)
        if source is not None:
            rules = [rule for rule in rules if rule.source == source]
        if enabled is not None:
            rules = [rule for rule in rules if rule.enabled == enabled]
        total = len(rules)
        start = (page - 1) * page_size
        return rules[start : start + page_size], total

    def set_rule_enabled(
        self,
        rule_id: str,
        enabled: bool,
        expected_version: str,
    ) -> tuple[Rule, str, bool]:
        """持久化规则的启用状态并返回更新后的规则、新版本和旧状态。

        使用乐观锁：expected_version 必须与当前版本一致，否则拒绝操作。
        同一规则重复设置为相同状态时直接返回（幂等）。
        """
        with self._lock:
            # 1. 版本检查 — 不匹配则拒绝
            current_version = self._repo.version()
            if expected_version != current_version:
                raise RuleVersionConflictError(current_version)
            # 2. 查找规则
            rule = self.get_rule_by_id(rule_id)
            if rule is None:
                raise KeyError(rule_id)
            # 3. 幂等检查 — 状态未变化则直接返回
            previous_enabled = rule.enabled
            if previous_enabled == enabled:
                return rule, current_version, previous_enabled
            # 4. 持久化整个类别的规则快照
            now = datetime.now().isoformat()
            category = rule.category
            saved_rules = [
                Rule(
                    id=r.id,
                    pattern=r.pattern,
                    pattern_type=r.pattern_type,
                    category=r.category,
                    risk_level=r.risk_level,
                    enabled=(not r.enabled) if r.id == rule_id else r.enabled,
                    description=r.description,
                    source=r.source,
                    created_at=r.created_at,
                    updated_at=now if r.id == rule_id else r.updated_at,
                )
                for r in self._rules[category]
            ]
            self._repo.save_category(category, saved_rules)

            rule.enabled = enabled
            rule.updated_at = now
            self._rules[category] = saved_rules
            return rule, self._repo.version(), previous_enabled

    def get_category_meta(self) -> list[RuleCategoryMeta]:
        """获取所有类别的规则统计与标签信息。"""
        labels = {
            RiskCategory.SEXUAL: "色情低俗",
            RiskCategory.VIOLENT: "暴力危险",
            RiskCategory.ADVERTISING: "广告引流",
            RiskCategory.SENSITIVE: "敏感话术",
        }
        descriptions = {
            RiskCategory.SEXUAL: "检测色情、低俗、性暗示等违规内容",
            RiskCategory.VIOLENT: "检测暴力、威胁、自残、危险行为等违规内容",
            RiskCategory.ADVERTISING: "检测广告推广、联系方式引流、重复营销话术等违规内容",
            RiskCategory.SENSITIVE: "检测政治敏感、违法违规、谣言等敏感话术",
        }
        with self._lock:
            return [
                RuleCategoryMeta(
                    category=category,
                    label=labels[category],
                    description=descriptions[category],
                    rule_count=len(self._rules.get(category, [])),
                    enabled_count=sum(rule.enabled for rule in self._rules.get(category, [])),
                )
                for category in RiskCategory
            ]

    def source_counts(self) -> list[dict]:
        """返回已加载规则的确定性来源计数。"""
        counts: dict[str, list[Rule]] = {}
        for rule in self.get_all_rules():
            counts.setdefault(rule.source, []).append(rule)
        return [
            {
                "source": source,
                "rule_count": len(rules),
                "enabled_count": sum(rule.enabled for rule in rules),
            }
            for source, rules in sorted(counts.items())
        ]

    def export_rules(self, category: RiskCategory) -> list[dict]:
        """将规则导出为可序列化的字典列表。"""
        return [
            {
                "id": rule.id,
                "pattern": rule.pattern,
                "pattern_type": rule.pattern_type,
                "category": rule.category.value,
                "risk_level": rule.risk_level.value,
                "enabled": rule.enabled,
                "description": rule.description,
                "source": rule.source,
            }
            for rule in self.get_all_rules(category)
        ]

    def import_rules(self, category: RiskCategory, rules_data: list[dict]) -> int:
        """向内存中添加导入的规则，兼容现有调用者。"""
        with self._lock:
            for item in rules_data:
                self._rules.setdefault(category, []).append(
                    Rule(
                        id=item.get("id", f"import-{datetime.now().timestamp()}"),
                        pattern=item["pattern"],
                        pattern_type=item.get("pattern_type", "keyword"),
                        category=category,
                        risk_level=RiskLevel(item.get("risk_level", "high")),
                        enabled=item.get("enabled", True),
                        description=item.get("description", ""),
                        source=item.get("source", ""),
                    )
                )
        return len(rules_data)
