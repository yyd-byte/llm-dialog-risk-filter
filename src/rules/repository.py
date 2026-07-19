"""规则文件加载与原子化保存（YAML 后端）。"""

import hashlib
import os
import tempfile
from pathlib import Path

import yaml

from src.decision.models import RiskCategory, RiskLevel
from src.rules.models import Rule
from src.utils.exceptions import RuleLoadError


class RuleRepository:
    """从 YAML 文件加载并按原子方式保存规则。

    每个风险类别对应一个 YAML 文件，写入时先写临时文件再原子替换，
    防止并发读取到不完整数据。
    """

    def __init__(self, rules_dir: str):
        self.rules_dir = Path(rules_dir)
        if not self.rules_dir.exists():
            raise RuleLoadError(f"Rules directory not found: {rules_dir}")

    def load_category(self, category: RiskCategory) -> list[Rule]:
        """加载单个类别的全部规则。

        Args:
            category: 风险类别枚举值。

        Returns:
            解析后的规则列表；文件不存在时返回空列表。
        """
        filepath = self.rules_dir / f"{category.value}.yaml"
        return self._parse_rule_file(filepath) if filepath.exists() else []

    def load_all(self) -> dict[RiskCategory, list[Rule]]:
        """加载全部四类规则，返回类别到规则列表的映射。"""
        return {category: self.load_category(category) for category in RiskCategory}

    def save_category(self, category: RiskCategory, rules: list[Rule]) -> None:
        """原子化保存单个类别的规则，同时保留文件元数据。

        写入流程：创建临时文件 → 写入内容 → fsync → 原子 rename。
        """
        filepath = self.rules_dir / f"{category.value}.yaml"
        existing = self._load_raw(filepath)
        data = {
            "category": category.value,
            "label": existing.get("label", self._category_label(category)),
            "description": existing.get("description", self._category_description(category)),
            "rules": [self._rule_to_dict(rule) for rule in rules],
        }
        content = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        self._atomic_write(filepath, content)

    def version(self) -> str:
        """基于四类规则 YAML 文件内容计算稳定版本摘要。"""
        digest = hashlib.sha256()
        for category in RiskCategory:
            path = self.rules_dir / f"{category.value}.yaml"
            digest.update(category.value.encode("utf-8"))
            digest.update(path.read_bytes() if path.exists() else b"")
        return f"sha256:{digest.hexdigest()}"

    def _parse_rule_file(self, filepath: Path) -> list[Rule]:
        """解析单个 YAML 规则文件为规则对象列表。"""
        data = self._load_raw(filepath)
        if not data or "rules" not in data:
            return []
        try:
            category = RiskCategory(data.get("category", "sensitive"))
            return [
                Rule(
                    id=item.get("id", ""),
                    pattern=item.get("pattern", ""),
                    pattern_type=item.get("pattern_type", "keyword"),
                    category=category,
                    risk_level=RiskLevel(item.get("risk_level", "high")),
                    enabled=item.get("enabled", True),
                    description=item.get("description", ""),
                    source=item.get("source", ""),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
                for item in data["rules"]
            ]
        except (TypeError, ValueError) as error:
            raise RuleLoadError(f"Invalid rule data in {filepath}: {error}") from error

    @staticmethod
    def _load_raw(filepath: Path) -> dict:
        """从 YAML 文件读取原始字典数据。"""
        try:
            with filepath.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except (OSError, yaml.YAMLError) as error:
            raise RuleLoadError(f"Failed to parse {filepath}: {error}") from error
        if not isinstance(data, dict):
            raise RuleLoadError(f"YAML root must be a mapping: {filepath}")
        return data

    @staticmethod
    def _atomic_write(filepath: Path, content: str) -> None:
        """原子化写入 YAML 文件：先写临时文件，fsync 后原子替换。"""
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{filepath.name}.", dir=filepath.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, filepath)
        except OSError as error:
            raise RuleLoadError(f"Failed to save {filepath}: {error}") from error
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _rule_to_dict(rule: Rule) -> dict:
        """将单条规则转换为可持久化的 YAML 字典。"""
        return {
            "id": rule.id,
            "pattern": rule.pattern,
            "pattern_type": rule.pattern_type,
            "risk_level": rule.risk_level.value,
            "enabled": rule.enabled,
            "description": rule.description,
            "source": rule.source,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }

    @staticmethod
    def _category_label(category: RiskCategory) -> str:
        """返回风险类别的中文标签。"""
        return {
            RiskCategory.SEXUAL: "色情低俗",
            RiskCategory.VIOLENT: "暴力危险",
            RiskCategory.ADVERTISING: "广告引流",
            RiskCategory.SENSITIVE: "敏感话术",
        }.get(category, "")

    @staticmethod
    def _category_description(category: RiskCategory) -> str:
        """返回风险类别的中文描述。"""
        return {
            RiskCategory.SEXUAL: "检测色情、低俗、性暗示等违规内容",
            RiskCategory.VIOLENT: "检测暴力、威胁、自残、危险行为等违规内容",
            RiskCategory.ADVERTISING: "检测广告推广、联系方式引流、重复营销话术等违规内容",
            RiskCategory.SENSITIVE: "检测政治敏感、违法违规、谣言等敏感话术",
        }.get(category, "")
