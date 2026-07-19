"""FastAPI 服务 — 以 REST API 形式提供内容风控流水线。

用法:
    python -m uvicorn src.api.server:app --reload --port 8000
"""

import json
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    PipelineRequest,
    PipelineResult,
    EvidenceItem,
    StatsOverview,
    DailyStatItem,
    CategoryStatItem,
    RuleItem,
    RuleMetadata,
    RuleMutationResponse,
    RulePage,
    RuleSourceSummary,
    SetRuleEnabledRequest,
    ReloadRequest,
    FeedbackRequest,
    FeedbackItem,
)
from src.audit.logger import AuditLogger, AuditRecord
from src.audit.rule_management import RuleManagementAuditLogger
from src.audit.statistics import StatisticsEngine
from src.decision.fusion import RiskFusion, fusion_config_from_dict
from src.decision.models import RiskLevel, RiskCategory
from src.desensitization.desensitizer import Desensitizer, DesensitizeConfig
from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.llm.client import LLMClient, LLMConfig
from src.output_check.checker import OutputChecker
from src.rules.manager import RuleManager, RuleVersionConflictError
from src.rules.repository import RuleRepository

# =============================================================================
# 应用初始化
# =============================================================================

app = FastAPI(
    title="LLM Dialog Risk Filter",
    description="大模型对话内容风控系统 API",
    version="0.1.0",
)

# 允许前端开发服务器（Vite 默认端口 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# =============================================================================
# 全局状态（启动时初始化）
# =============================================================================

_normalizer: Optional[TextNormalizer] = None
_rule_detector: Optional[RuleDetector] = None
_rule_manager: Optional[RuleManager] = None
_semantic_detector: Optional[SemanticDetector] = None
_fusion: Optional[RiskFusion] = None
_desensitizer: Optional[Desensitizer] = None
_output_checker: Optional[OutputChecker] = None
_audit_logger: Optional[AuditLogger] = None
_rule_management_audit: Optional[RuleManagementAuditLogger] = None
_rules_admin_token: str = ""
_stats_engine: Optional[StatisticsEngine] = None
_llm_client: Optional[LLMClient] = None
_config: dict = {}

# 内存反馈存储（后续可改为文件持久化）
_feedback_store: list[dict] = []

# 类别颜色映射（供前端使用）
_CATEGORY_COLORS = {
    "sexual": "#ec4899",
    "violent": "#ef4444",
    "advertising": "#f59e0b",
    "sensitive": "#8b5cf6",
}

_CATEGORY_LABELS = {
    "sexual": "色情低俗",
    "violent": "暴力危险",
    "advertising": "广告引流",
    "sensitive": "敏感话术",
}


# =============================================================================
# 生命周期
# =============================================================================


@app.on_event("startup")
def startup():
    """初始化所有组件。"""
    global _normalizer, _rule_detector, _rule_manager, _semantic_detector
    global _fusion, _desensitizer, _output_checker, _audit_logger, _rule_management_audit
    global _stats_engine, _llm_client, _config, _rules_admin_token

    project_root = Path(__file__).resolve().parent.parent.parent

    # 加载配置
    config_path = project_root / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    # 从环境变量注入敏感密钥（防止泄露到 GitHub）
    # 优先从 .env 文件加载，其次从系统环境变量
    import os as _os

    _env_file = project_root / ".env"
    if _env_file.exists():
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _val = _line.split("=", 1)
                    _os.environ.setdefault(_key.strip(), _val.strip())
    if _os.environ.get("DEEPSEEK_API_KEY"):
        _config["llm"]["api_key"] = _os.environ["DEEPSEEK_API_KEY"]
    if _os.environ.get("SILICONFLOW_API_KEY"):
        _config.setdefault("semantic_detection", {}).setdefault("api", {})
        _config["semantic_detection"]["api"]["api_key"] = _os.environ["SILICONFLOW_API_KEY"]
    _rules_admin_token = _os.environ.get("RULES_ADMIN_TOKEN", "")

    # Normalizer（文本规范化器）
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

    _normalizer = TextNormalizer(
        NormalizerConfig(
            bypass_map=bypass_map,
            confusable_map=confusable_map,
            pinyin_map=pinyin_map,
            traditional_simplified_map=traditional_simplified_map,
            abbreviation_map=abbreviation_map,
            decomposition_map=decomposition_map,
        )
    )

    # 规则组件
    rules_dir = project_root / _config["rule_detection"]["rules_dir"]
    _rule_manager = RuleManager(RuleRepository(str(rules_dir)))
    fusion_config = fusion_config_from_dict(_config.get("risk_fusion", {}))
    _rule_detector = RuleDetector(
        _rule_manager,
        level_confidence=fusion_config.rule_confidence,
    )

    # 语义检测
    sem_cfg = _config["semantic_detection"]
    api_mode = sem_cfg.get("mode", "local") == "api"
    _semantic_detector = SemanticDetector(
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
        import os as _os

        if not _os.environ.get("HF_ENDPOINT"):
            _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        _semantic_detector.load_model()
        print(f"语义模型已加载: {sem_cfg['model_name']}")
    except Exception as e:
        print(f"语义模型未加载（回退到纯规则模式）: {e}")

    # 融合决策
    _fusion = RiskFusion(fusion_config)

    # 脱敏器
    ds_cfg = _config.get("desensitization", {})
    _desensitizer = Desensitizer(
        DesensitizeConfig(
            mode=ds_cfg.get("mode", "semantic"),
            replacement_char=ds_cfg.get("replacement_char", "*"),
            keep_first_last=ds_cfg.get("keep_first_last", True),
            category_labels=ds_cfg.get("category_labels", {}),
            fallback_label=ds_cfg.get("fallback_label", "[违规内容]"),
            rewrite_prompt=ds_cfg.get("rewrite_prompt", ""),
        )
    )
    # 输出复检
    _output_checker = OutputChecker(
        _rule_detector,
        _semantic_detector,
        _fusion,
        block_message=_config["output_check"]["output_block_message"],
        desensitizer=_desensitizer,
    )

    # 审计日志
    audit_cfg = _config["audit"]
    _audit_logger = AuditLogger(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )
    _rule_management_audit = RuleManagementAuditLogger(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # 统计引擎
    _stats_engine = StatisticsEngine(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # LLM 客户端（尝试连接，连接失败不影响核心功能）
    llm_cfg = _config["llm"]
    try:
        _llm_client = LLMClient(
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
        _llm_client = None

    rule_count = sum(1 for _ in _rule_manager.get_enabled_rules())
    print(f"规则已加载: {rule_count} 条已启用")
    print("API 服务就绪 [OK]")


# =============================================================================
# POST /api/pipeline/check — 流水线检测
# =============================================================================


@app.post("/api/pipeline/check", response_model=PipelineResult)
def pipeline_check(req: PipelineRequest):
    """对用户输入执行完整的内容风控流水线检测。"""
    assert _normalizer is not None
    assert _rule_detector is not None
    assert _semantic_detector is not None
    assert _fusion is not None
    assert _desensitizer is not None
    assert _output_checker is not None
    assert _audit_logger is not None

    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    text = req.input

    record = AuditRecord(
        request_id=request_id,
        original_input=text,
    )

    # 步骤 1: 文本规范化
    normalized = _normalizer.normalize(text)
    record.normalized_input = normalized.normalized
    # 构建规范化证据：检测变化内容
    normalize_changes = []
    if text != normalized.normalized:
        if text.lower() != normalized.normalized:
            normalize_changes.append("大小写转换")
        if len(text) != len(normalized.normalized):
            normalize_changes.append("分隔符剥离/空格合并")
        # 检查易混淆字符变化
        changed_chars = sum(1 for a, b in zip(text, normalized.normalized) if a != b)
        if changed_chars > 0:
            normalize_changes.append(f"{changed_chars}处字符已规范化")
    norm_explanation = "、".join(normalize_changes) if normalize_changes else "无需规范化"

    # 步骤 2: 规则检测
    rule_evidence = _rule_detector.detect(normalized.normalized)

    # 步骤 3: 语义检测
    semantic_evidence = _semantic_detector.detect(normalized.normalized)

    # 步骤 4: 风险融合
    risk_result = _fusion.evaluate_input(rule_evidence, semantic_evidence)
    record.input_risk_level = risk_result.risk_level.value
    record.input_risk_category = (
        risk_result.risk_category.value if risk_result.risk_category else None
    )
    record.input_confidence = risk_result.confidence
    record.input_action = risk_result.action

    # 构建证据链：规范化 → 规则匹配 → 语义匹配 → 融合决策
    evidence_chain = []

    # 1. 规范化证据
    evidence_chain.append(
        {
            "source": "rule",
            "category": risk_result.risk_category.value
            if risk_result.risk_category
            else "sensitive",
            "confidence": 0.0,
            "matched_pattern": "",
            "matched_text": "",
            "explanation": f"文本规范化: {norm_explanation}",
            "step": "normalize",
            "metadata": {
                "original_length": len(text),
                "normalized_length": len(normalized.normalized),
                "changes": normalize_changes,
            },
        }
    )

    # 2. 检测证据（规则 + 语义）
    for e in risk_result.evidence_chain:
        evidence_chain.append(
            {
                "source": e.source.value,
                "category": e.category.value if e.category else "",
                "confidence": e.confidence,
                "matched_pattern": e.matched_pattern,
                "matched_text": e.matched_text,
                "explanation": e.explanation,
                "step": e.step or ("rule" if e.source.value == "rule" else "semantic"),
                "metadata": e.metadata,
            }
        )

    # 3. 融合决策证据
    evidence_chain.append(
        {
            "source": "semantic",
            "category": risk_result.risk_category.value if risk_result.risk_category else "",
            "confidence": risk_result.confidence,
            "matched_pattern": "",
            "matched_text": "",
            "explanation": (
                f"融合决策: 规则层({len(rule_evidence)}条) + 语义层({len(semantic_evidence)}条) "
                f"→ 综合置信度 {risk_result.confidence:.0%} → "
                f"风险等级 {risk_result.risk_level.value.upper()}"
            ),
            "step": "fusion",
            "metadata": {
                "rule_count": len(rule_evidence),
                "semantic_count": len(semantic_evidence),
                "rule_weight": _fusion.config.rule_weight,
                "semantic_weight": _fusion.config.semantic_weight,
                "high_threshold": _fusion.config.high_threshold,
                "medium_threshold": _fusion.config.medium_threshold,
            },
        }
    )

    record.input_evidence = evidence_chain

    # 步骤 5: 按风险等级执行处置
    if risk_result.risk_level == RiskLevel.HIGH:
        # 直接拦截
        record.final_output = "抱歉，您的请求包含不适宜内容，无法处理。"
        record.total_duration_ms = (time.time() - start_time) * 1000
        _audit_logger.log(record)
        return _build_pipeline_result(record)

    elif risk_result.risk_level == RiskLevel.MEDIUM:
        # 脱敏处理（模式为 rewrite 时调用 LLM 改写）
        llm_rewrite = None
        if _desensitizer.config.mode == "rewrite" and _llm_client:

            def _rewrite(prompt: str) -> str:
                resp = _llm_client.chat(prompt)
                return resp.text if resp.success else ""

            llm_rewrite = _rewrite
        des_result = _desensitizer.desensitize(
            normalized.normalized, risk_result, llm_call=llm_rewrite
        )
        safe_input = des_result.desensitized
        record.desensitized_input = safe_input
        # 添加脱敏证据
        for frag in des_result.replaced_fragments:
            record.input_evidence.append(
                {
                    "source": "rule",
                    "category": frag.get("category", ""),
                    "confidence": 1.0,
                    "matched_pattern": frag.get("original", ""),
                    "matched_text": frag.get("original", ""),
                    "explanation": f"片段脱敏: '{frag.get('original', '')}' → '{frag.get('replacement', '')}' ({frag.get('reason', '')})",
                    "step": "desensitize",
                    "metadata": {
                        "original_fragment": frag.get("original", ""),
                        "replacement": frag.get("replacement", ""),
                        "was_rewritten": des_result.was_rewritten,
                    },
                }
            )
    else:
        safe_input = text

    # 步骤 6: 调用大模型
    if _llm_client:
        llm_resp = _llm_client.chat(safe_input)
        record.llm_called = True
        record.llm_model = _llm_client.config.model
        llm_output = llm_resp.text if llm_resp.success else f"[LLM Error: {llm_resp.error}]"
    else:
        llm_output = f'[模拟大模型回复] 针对您的问题"{text[:30]}"，这是一个示例回答。'
        record.llm_called = False
        record.llm_model = "demo-simulation"

    record.llm_output = llm_output

    # 步骤 7: 输出复检
    output_result = _output_checker.check(llm_output)
    record.output_risk_level = (
        output_result.risk_result.risk_level.value if output_result.risk_result else "low"
    )
    record.output_passed = output_result.is_safe
    record.output_blocked = not output_result.is_safe
    record.final_output = output_result.final_output

    record.total_duration_ms = (time.time() - start_time) * 1000
    _audit_logger.log(record)
    return _build_pipeline_result(record)


def _build_pipeline_result(record: AuditRecord) -> PipelineResult:
    """将 AuditRecord 转换为 PipelineResult 响应。"""
    return PipelineResult(
        requestId=record.request_id,
        timestamp=record.timestamp,
        originalInput=record.original_input,
        normalizedInput=record.normalized_input,
        riskLevel=record.input_risk_level,
        riskCategory=record.input_risk_category,
        confidence=record.input_confidence,
        action=record.input_action,
        desensitizedInput=record.desensitized_input,
        llmCalled=record.llm_called,
        llmOutput=record.llm_output,
        outputRiskLevel=record.output_risk_level,
        outputBlocked=record.output_blocked,
        finalOutput=record.final_output,
        durationMs=round(record.total_duration_ms, 1),
        evidenceChain=[
            EvidenceItem(
                source=ev["source"],
                category=ev["category"],
                confidence=ev["confidence"],
                matchedPattern=ev.get("matched_pattern", ""),
                matchedText=ev.get("matched_text", ""),
                explanation=ev.get("explanation", ""),
                step=ev.get("step", ""),
                metadata=ev.get("metadata", {}),
            )
            for ev in record.input_evidence
        ],
    )


# =============================================================================
# GET /api/stats/overview — 统计概览
# =============================================================================


@app.get("/api/stats/overview", response_model=StatsOverview)
def stats_overview(days: int = 7):
    """获取聚合统计概览。"""
    assert _stats_engine is not None

    overview = _stats_engine.get_overview(days=days)

    daily_stats = [
        DailyStatItem(
            date=ds.date,
            blocked=ds.input_blocked,
            desensitized=ds.input_desensitized,
            passed=ds.input_passed,
            outputBlocked=ds.output_blocked,
        )
        for ds in overview.daily_stats
    ]

    category_stats = [
        CategoryStatItem(
            category=cat,
            label=_CATEGORY_LABELS.get(cat, cat),
            count=count,
            color=_CATEGORY_COLORS.get(cat, "#64748b"),
        )
        for cat, count in overview.top_categories
    ]

    return StatsOverview(
        totalRequests=overview.total_requests,
        blockRate=round(overview.block_rate, 4),
        falsePositiveRate=round(overview.false_positive_rate, 4),
        totalLlmCalls=overview.total_llm_calls,
        outputBlockRate=round(overview.output_block_rate, 4),
        dailyStats=daily_stats,
        categoryStats=category_stats,
    )


# =============================================================================
# 规则管理辅助函数
# =============================================================================


def _rule_item(rule) -> RuleItem:
    """将内部规则对象转换为公共 API 表示。"""
    return RuleItem(
        id=rule.id,
        pattern=rule.pattern,
        patternType=rule.pattern_type,
        category=rule.category.value,
        riskLevel=rule.risk_level.value,
        enabled=rule.enabled,
        description=rule.description,
        source=rule.source,
        updatedAt=rule.updated_at,
    )


def _rule_metadata() -> RuleMetadata:
    """从当前活跃的管理器快照构建规则元数据。"""
    assert _rule_manager is not None
    categories = [
        {
            "category": meta.category.value,
            "label": meta.label,
            "ruleCount": meta.rule_count,
            "enabledCount": meta.enabled_count,
        }
        for meta in _rule_manager.get_category_meta()
    ]
    sources = [
        RuleSourceSummary(
            source=item["source"],
            ruleCount=item["rule_count"],
            enabledCount=item["enabled_count"],
        )
        for item in _rule_manager.source_counts()
    ]
    total = sum(item["ruleCount"] for item in categories)
    enabled_total = sum(item["enabledCount"] for item in categories)
    return RuleMetadata(
        version=_rule_manager.rebuild_version(),
        total=total,
        enabledTotal=enabled_total,
        categories=categories,
        sources=sources,
    )


def _require_rules_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """未配置本地管理令牌时拒绝规则管理写入操作。"""
    if not _rules_admin_token:
        raise HTTPException(status_code=503, detail="Rule management unavailable")
    if x_admin_token is None or not secrets.compare_digest(x_admin_token, _rules_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


# =============================================================================
# GET /api/rules — 规则列表
# =============================================================================


@app.get("/api/rules", response_model=RulePage)
def list_rules(
    page: int = 1,
    page_size: int = 50,
    category: str | None = None,
    source: str | None = None,
    enabled: bool | None = None,
):
    """获取一页经过过滤的规则列表。"""
    assert _rule_manager is not None
    if page < 1 or not 1 <= page_size <= 200:
        raise HTTPException(status_code=422, detail="Invalid pagination")
    try:
        category_enum = RiskCategory(category) if category else None
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid risk category") from error
    rules, total = _rule_manager.list_rules(category_enum, source, enabled, page, page_size)
    return RulePage(
        items=[_rule_item(rule) for rule in rules],
        page=page,
        pageSize=page_size,
        total=total,
        version=_rule_manager.rebuild_version(),
    )


@app.get("/api/rules/metadata", response_model=RuleMetadata)
def rule_metadata():
    """获取当前规则集的版本和来源摘要。"""
    return _rule_metadata()


@app.patch("/api/rules/{rule_id}/enabled", response_model=RuleMutationResponse)
def set_rule_enabled(
    rule_id: str,
    request: SetRuleEnabledRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """持久化显式启用状态并立即重建检测器缓存。"""
    _require_rules_admin_token(x_admin_token)
    assert _rule_manager is not None and _rule_detector is not None
    assert _rule_management_audit is not None
    try:
        rule, version, previous_enabled = _rule_manager.set_rule_enabled(
            rule_id,
            request.enabled,
            request.expectedVersion,
        )
    except RuleVersionConflictError as error:
        raise HTTPException(status_code=409, detail={"version": str(error)}) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Rule not found") from error
    state_changed = previous_enabled != rule.enabled
    if state_changed:
        _rule_detector.rebuild_cache()
        _rule_management_audit.log_enabled_change(
            rule.id,
            rule.category.value,
            rule.source,
            previous_enabled,
            rule.enabled,
            request.expectedVersion,
            version,
        )
    return RuleMutationResponse(item=_rule_item(rule), version=version)


@app.post("/api/rules/reload", response_model=RuleMetadata)
def reload_rules(
    request: ReloadRequest,
    _: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """重载 YAML 规则并重建检测器缓存，无需重启 API 服务。"""
    _require_rules_admin_token(_)
    assert _rule_manager is not None and _rule_detector is not None
    assert _rule_management_audit is not None
    version_before = _rule_manager.rebuild_version()
    if request.expectedVersion and request.expectedVersion != version_before:
        raise HTTPException(status_code=409, detail={"version": version_before})
    try:
        _rule_manager.reload()
        _rule_detector.rebuild_cache()
    except Exception as error:
        raise HTTPException(status_code=500, detail="Rule reload failed") from error
    metadata = _rule_metadata()
    _rule_management_audit.log_reload(
        version_before,
        metadata.version,
        metadata.total,
        metadata.enabledTotal,
    )
    return metadata


# =============================================================================
# POST /api/feedback — 意见反馈
# =============================================================================


@app.post("/api/feedback", response_model=FeedbackItem)
def submit_feedback(req: FeedbackRequest):
    """提交误判反馈。"""
    feedback_id = str(uuid.uuid4())[:8]
    record = {
        "id": feedback_id,
        "timestamp": datetime.now().isoformat(),
        "type": req.type,
        "status": "pending",
        "sample": req.sample,
        "suggestion": req.suggestion,
        "requestId": req.requestId,
        "correctCategory": req.correctCategory,
    }
    _feedback_store.append(record)

    # 持久化到反馈 JSONL 文件
    feedback_path = Path(__file__).resolve().parent.parent.parent / "data" / "feedback"
    feedback_path.mkdir(parents=True, exist_ok=True)
    with open(feedback_path / "feedback.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return FeedbackItem(
        id=feedback_id,
        timestamp=record["timestamp"],
        type=record["type"],
        status="pending",
        sample=record["sample"],
        suggestion=record["suggestion"],
    )


# =============================================================================
# GET /api/audit — 审计日志
# =============================================================================


@app.get("/api/audit", response_model=list[dict])
def list_audit_logs(limit: int = 50):
    """获取最近的审计日志条目。"""
    assert _audit_logger is not None

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = _audit_logger.log_dir / f"audit-{today}.jsonl"
    records: list[dict] = []

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    inp = entry.get("input", {})
                    out = entry.get("output", {})
                    perf = entry.get("performance", {})
                    llm = entry.get("llm", {})
                    records.append(
                        {
                            "requestId": entry.get("request_id", ""),
                            "timestamp": entry.get("timestamp", ""),
                            "action": inp.get("action", "pass"),
                            "riskLevel": inp.get("risk_level", "low"),
                            "category": inp.get("risk_category"),
                            "evidenceCount": inp.get("evidence_count", 0),
                            "llmCalled": llm.get("called", False),
                            "outputBlocked": out.get("blocked", False),
                            "durationMs": perf.get("total_duration_ms", 0),
                        }
                    )
                except json.JSONDecodeError:
                    continue

    # 返回最新的记录，按 limit 截取
    records.reverse()
    return records[:limit]


# =============================================================================
# 健康检查
# =============================================================================


@app.get("/api/health")
def health():
    """健康检查端点。"""
    assert _rule_manager is not None
    return {
        "status": "ok",
        "rulesLoaded": sum(1 for _ in _rule_manager.get_enabled_rules()),
        "semanticAvailable": _semantic_detector.is_available if _semantic_detector else False,
        "llmAvailable": _llm_client is not None,
    }
