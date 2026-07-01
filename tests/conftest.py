"""Shared test fixtures."""

import pytest
from pathlib import Path
import sys
import tempfile
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.rules.repository import RuleRepository
from src.rules.manager import RuleManager
from src.decision.fusion import RiskFusion
from src.desensitization.desensitizer import Desensitizer
from src.output_check.checker import OutputChecker
from src.audit.logger import AuditLogger, AuditRecord


@pytest.fixture
def normalizer():
    """Create a TextNormalizer with default config."""
    return TextNormalizer()


@pytest.fixture
def rule_manager():
    """Create a RuleManager with temporary rule files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test rule file
        rules_dir = Path(tmpdir) / "rules"
        rules_dir.mkdir()

        test_rules = {
            "category": "sensitive",
            "label": "测试规则",
            "description": "测试用规则",
            "rules": [
                {
                    "id": "test-kw-001",
                    "pattern": "违规词",
                    "pattern_type": "keyword",
                    "risk_level": "high",
                    "enabled": True,
                    "description": "测试关键词",
                },
                {
                    "id": "test-re-001",
                    "pattern": r"违规\d+号",
                    "pattern_type": "regex",
                    "risk_level": "high",
                    "enabled": True,
                    "description": "测试正则",
                },
                {
                    "id": "test-kw-002",
                    "pattern": "广告测试",
                    "pattern_type": "keyword",
                    "risk_level": "medium",
                    "enabled": True,
                    "description": "测试中风险词",
                },
            ],
        }

        with open(rules_dir / "sensitive.yaml", "w", encoding="utf-8") as f:
            yaml.dump(test_rules, f, allow_unicode=True)

        # Create empty files for other categories
        for cat in ["sexual", "violent", "advertising"]:
            with open(rules_dir / f"{cat}.yaml", "w", encoding="utf-8") as f:
                yaml.dump({"category": cat, "label": cat, "description": "", "rules": []}, f)

        repo = RuleRepository(str(rules_dir))
        yield RuleManager(repo)


@pytest.fixture
def rule_detector(rule_manager):
    """Create a RuleDetector with test rules."""
    return RuleDetector(rule_manager)


@pytest.fixture
def semantic_detector():
    """Create a SemanticDetector (no model loaded)."""
    return SemanticDetector()


@pytest.fixture
def fusion():
    """Create a RiskFusion with default config."""
    return RiskFusion()


@pytest.fixture
def desensitizer():
    """Create a Desensitizer with default config."""
    return Desensitizer()


@pytest.fixture
def output_checker(rule_detector, semantic_detector, fusion):
    """Create an OutputChecker."""
    return OutputChecker(rule_detector, semantic_detector, fusion)


@pytest.fixture
def audit_logger():
    """Create an AuditLogger with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield AuditLogger(log_dir=tmpdir)


@pytest.fixture
def sample_normal_texts():
    """Normal text samples that should not trigger any rules."""
    return [
        "今天天气真好，适合出去散步",
        "请问Python的装饰器怎么用",
        "推荐一本好看的小说",
        "最近在学习机器学习，有什么建议吗",
    ]


@pytest.fixture
def sample_risk_texts():
    """Risk text samples (placeholder)."""
    return [
        "违规词测试内容",
        "这是违规123号的内容",
        "广告测试内容在这里",
    ]