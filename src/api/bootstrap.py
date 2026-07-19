"""API 服务启动初始化 — 创建并配置全部组件。

将各组件的构造逻辑集中于此，供 server.py 在 startup 事件中调用。
"""

import os as _os
from pathlib import Path
from typing import Optional

import yaml

from src.audit.logger import AuditLogger
from src.audit.rule_management import RuleManagementAuditLogger
from src.audit.statistics import StatisticsEngine
from src.decision.fusion import RiskFusion, fusion_config_from_dict
from src.desensitization.desensitizer import Desensitizer, DesensitizeConfig
from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.llm.client import LLMClient, LLMConfig
from src.output_check.checker import OutputChecker
from src.rules.manager import RuleManager
from src.rules.repository import RuleRepository


# =============================================================================
# 全局组件单例
# =============================================================================

_components: Optional["AppComponents"] = None


class AppComponents:
    """API 服务所需的全部组件容器。

    在 startup 事件中创建并注入到各路由模块。
    """

    normalizer: TextNormalizer
    rule_detector: RuleDetector
    rule_manager: RuleManager
    semantic_detector: SemanticDetector
    fusion: RiskFusion
    desensitizer: Desensitizer
    output_checker: OutputChecker
    audit_logger: AuditLogger
    rule_management_audit: RuleManagementAuditLogger
    stats_engine: StatisticsEngine
    llm_client: LLMClient | None
    config: dict
    rules_admin_token: str
    feedback_store: list[dict]

    def __init__(
        self,
        normalizer: TextNormalizer,
        rule_detector: RuleDetector,
        rule_manager: RuleManager,
        semantic_detector: SemanticDetector,
        fusion: RiskFusion,
        desensitizer: Desensitizer,
        output_checker: OutputChecker,
        audit_logger: AuditLogger,
        rule_management_audit: RuleManagementAuditLogger,
        stats_engine: StatisticsEngine,
        llm_client: LLMClient | None,
        config: dict,
        rules_admin_token: str,
    ):
        self.normalizer = normalizer
        self.rule_detector = rule_detector
        self.rule_manager = rule_manager
        self.semantic_detector = semantic_detector
        self.fusion = fusion
        self.desensitizer = desensitizer
        self.output_checker = output_checker
        self.audit_logger = audit_logger
        self.rule_management_audit = rule_management_audit
        self.stats_engine = stats_engine
        self.llm_client = llm_client
        self.config = config
        self.rules_admin_token = rules_admin_token
        self.feedback_store = []

    @classmethod
    def init(cls, components: "AppComponents") -> None:
        """初始化全局组件单例。"""
        global _components
        _components = components

    @classmethod
    def get(cls) -> "AppComponents":
        """获取全局组件单例。

        Returns:
            AppComponents 实例。

        Raises:
            AssertionError: 尚未调用 init() 时抛出。
        """
        assert _components is not None, "AppComponents 尚未初始化，请先调用 AppComponents.init()"
        return _components


# =============================================================================
# 启动初始化函数
# =============================================================================


def bootstrap(project_root: Path) -> AppComponents:
    """创建并配置全部组件。

    将原 server.py 中 startup() 的全部构造逻辑迁移至此，
    返回填充完毕的 AppComponents 实例。

    Args:
        project_root: 项目根目录路径。

    Returns:
        包含全部已初始化组件的 AppComponents 实例。
    """
    # ---- 加载配置 -----------------------------------------------------------
    config_path = project_root / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 从环境变量注入敏感密钥（防止泄露到 GitHub）
    # 优先从 .env 文件加载，其次从系统环境变量
    _env_file = project_root / ".env"
    if _env_file.exists():
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _val = _line.split("=", 1)
                    _os.environ.setdefault(_key.strip(), _val.strip())
    if _os.environ.get("DEEPSEEK_API_KEY"):
        config["llm"]["api_key"] = _os.environ["DEEPSEEK_API_KEY"]
    if _os.environ.get("SILICONFLOW_API_KEY"):
        config.setdefault("semantic_detection", {}).setdefault("api", {})
        config["semantic_detection"]["api"]["api_key"] = _os.environ["SILICONFLOW_API_KEY"]
    rules_admin_token = _os.environ.get("RULES_ADMIN_TOKEN", "")

    # ---- Normalizer（文本规范化器）-------------------------------------------
    bypass_map: dict[str, str] = {}
    bypass_path = project_root / "config" / "bypass_variants.yaml"
    if bypass_path.exists():
        with open(bypass_path, "r", encoding="utf-8") as f:
            bypass_map = yaml.safe_load(f) or {}

    confusable_map: dict[str, str] = {}
    confusable_path = project_root / "config" / "confusable_chars.yaml"
    if confusable_path.exists():
        with open(confusable_path, "r", encoding="utf-8") as f:
            confusable_map = yaml.safe_load(f) or {}

    pinyin_map: dict[str, str] = {}
    pinyin_path = project_root / "config" / "pinyin_variants.yaml"
    if pinyin_path.exists():
        with open(pinyin_path, "r", encoding="utf-8") as f:
            pinyin_map = yaml.safe_load(f) or {}

    traditional_simplified_map: dict[str, str] = {}
    ts_path = project_root / "config" / "traditional_simplified.yaml"
    if ts_path.exists():
        with open(ts_path, "r", encoding="utf-8") as f:
            traditional_simplified_map = yaml.safe_load(f) or {}

    abbreviation_map: dict[str, str] = {}
    abbr_path = project_root / "config" / "abbreviation_map.yaml"
    if abbr_path.exists():
        with open(abbr_path, "r", encoding="utf-8") as f:
            abbreviation_map = yaml.safe_load(f) or {}

    decomposition_map: dict[str, str] = {}
    decomp_path = project_root / "config" / "decomposition_map.yaml"
    if decomp_path.exists():
        with open(decomp_path, "r", encoding="utf-8") as f:
            decomposition_map = yaml.safe_load(f) or {}

    normalizer = TextNormalizer(
        NormalizerConfig(
            bypass_map=bypass_map,
            confusable_map=confusable_map,
            pinyin_map=pinyin_map,
            traditional_simplified_map=traditional_simplified_map,
            abbreviation_map=abbreviation_map,
            decomposition_map=decomposition_map,
        )
    )

    # ---- 规则组件 -----------------------------------------------------------
    rules_dir = project_root / config["rule_detection"]["rules_dir"]
    rule_manager = RuleManager(RuleRepository(str(rules_dir)))
    fusion_config = fusion_config_from_dict(config.get("risk_fusion", {}))
    rule_detector = RuleDetector(
        rule_manager,
        level_confidence=fusion_config.rule_confidence,
    )

    # ---- 语义检测 -----------------------------------------------------------
    sem_cfg = config["semantic_detection"]
    api_mode = sem_cfg.get("mode", "local") == "api"
    semantic_detector = SemanticDetector(
        model_name=sem_cfg.get("model_name", "BAAI/bge-small-zh-v1.5"),
        confidence_threshold=sem_cfg["confidence_threshold"],
        device=sem_cfg.get("device", "cpu"),
        category_references=sem_cfg.get("category_references"),
        api_mode=api_mode,
        api_config=sem_cfg.get("api") if api_mode else None,
    )
    # 尝试加载语义模型（加载失败不影响核心功能）
    try:
        # 国内网络环境使用 HuggingFace 镜像加速
        if not _os.environ.get("HF_ENDPOINT"):
            _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        semantic_detector.load_model()
        print(f"语义模型已加载: {sem_cfg['model_name']}")
    except Exception as e:
        print(f"语义模型未加载（回退到纯规则模式）: {e}")

    # ---- 融合决策 -----------------------------------------------------------
    fusion = RiskFusion(fusion_config)

    # ---- 脱敏器 -------------------------------------------------------------
    ds_cfg = config.get("desensitization", {})
    desensitizer = Desensitizer(
        DesensitizeConfig(
            mode=ds_cfg.get("mode", "semantic"),
            replacement_char=ds_cfg.get("replacement_char", "*"),
            keep_first_last=ds_cfg.get("keep_first_last", True),
            category_labels=ds_cfg.get("category_labels", {}),
            fallback_label=ds_cfg.get("fallback_label", "[违规内容]"),
            rewrite_prompt=ds_cfg.get("rewrite_prompt", ""),
        )
    )

    # ---- 输出复检 -----------------------------------------------------------
    output_checker = OutputChecker(
        rule_detector,
        semantic_detector,
        fusion,
        block_message=config["output_check"]["output_block_message"],
        desensitizer=desensitizer,
    )

    # ---- 审计日志 -----------------------------------------------------------
    audit_cfg = config["audit"]
    audit_logger = AuditLogger(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )
    rule_management_audit = RuleManagementAuditLogger(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # ---- 统计引擎 -----------------------------------------------------------
    stats_engine = StatisticsEngine(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # ---- LLM 客户端（尝试连接，连接失败不影响核心功能）----------------------
    llm_cfg = config["llm"]
    llm_client: LLMClient | None = None
    try:
        llm_client = LLMClient(
            LLMConfig(
                provider=llm_cfg["provider"],
                base_url=llm_cfg["base_url"],
                model=llm_cfg["model"],
                api_key=llm_cfg["api_key"],
                timeout=llm_cfg["timeout"],
                max_tokens=llm_cfg["max_tokens"],
            )
        )
        print(f"LLM 客户端已配置: {llm_cfg['provider']} / {llm_cfg['model']}")
    except Exception as e:
        print(f"LLM 客户端未配置（模拟模式）: {e}")

    rule_count = sum(1 for _ in rule_manager.get_enabled_rules())
    print(f"规则已加载: {rule_count} 条已启用")

    return AppComponents(
        normalizer=normalizer,
        rule_detector=rule_detector,
        rule_manager=rule_manager,
        semantic_detector=semantic_detector,
        fusion=fusion,
        desensitizer=desensitizer,
        output_checker=output_checker,
        audit_logger=audit_logger,
        rule_management_audit=rule_management_audit,
        stats_engine=stats_engine,
        llm_client=llm_client,
        config=config,
        rules_admin_token=rules_admin_token,
    )
