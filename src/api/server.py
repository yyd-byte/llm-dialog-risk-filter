"""FastAPI server — exposes the content filtering pipeline as REST API.

Usage:
    python -m uvicorn src.api.server:app --reload --port 8000
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    PipelineRequest,
    PipelineResult,
    EvidenceItem,
    StatsOverview,
    DailyStatItem,
    CategoryStatItem,
    RuleItem,
    FeedbackRequest,
    FeedbackItem,
)
from src.audit.logger import AuditLogger, AuditRecord
from src.audit.statistics import StatisticsEngine
from src.decision.fusion import RiskFusion
from src.decision.models import RiskLevel, RiskCategory
from src.desensitization.desensitizer import Desensitizer
from src.detection.normalizer import TextNormalizer
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.llm.client import LLMClient, LLMConfig
from src.output_check.checker import OutputChecker
from src.rules.manager import RuleManager
from src.rules.repository import RuleRepository

# =============================================================================
# App setup
# =============================================================================

app = FastAPI(
    title="LLM Dialog Risk Filter",
    description="大模型对话内容风控系统 API",
    version="0.1.0",
)

# Allow frontend dev server (Vite default port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Global state (initialized at startup)
# =============================================================================

_normalizer: Optional[TextNormalizer] = None
_rule_detector: Optional[RuleDetector] = None
_rule_manager: Optional[RuleManager] = None
_semantic_detector: Optional[SemanticDetector] = None
_fusion: Optional[RiskFusion] = None
_desensitizer: Optional[Desensitizer] = None
_output_checker: Optional[OutputChecker] = None
_audit_logger: Optional[AuditLogger] = None
_stats_engine: Optional[StatisticsEngine] = None
_llm_client: Optional[LLMClient] = None
_config: dict = {}

# In-memory feedback store (replace with file-based later)
_feedback_store: list[dict] = []

# Category color map for frontend
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
# Lifecycle
# =============================================================================

@app.on_event("startup")
def startup():
    """Initialize all components."""
    global _normalizer, _rule_detector, _rule_manager, _semantic_detector
    global _fusion, _desensitizer, _output_checker, _audit_logger
    global _stats_engine, _llm_client, _config

    project_root = Path(__file__).resolve().parent.parent.parent

    # Load config
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

    # Normalizer
    _normalizer = TextNormalizer()

    # Rules
    rules_dir = project_root / _config["rule_detection"]["rules_dir"]
    _rule_manager = RuleManager(RuleRepository(str(rules_dir)))
    _rule_detector = RuleDetector(_rule_manager)

    # Semantic
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
    # Try to load the semantic model (non-fatal if unavailable)
    try:
        # 国内网络环境使用 HuggingFace 镜像加速
        import os as _os
        if not _os.environ.get("HF_ENDPOINT"):
            _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        _semantic_detector.load_model()
        print(f"语义模型已加载: {sem_cfg['model_name']}")
    except Exception as e:
        print(f"语义模型未加载（回退到纯规则模式）: {e}")

    # Fusion
    _fusion = RiskFusion()

    # Desensitizer
    _desensitizer = Desensitizer()

    # Output checker
    _output_checker = OutputChecker(
        _rule_detector, _semantic_detector, _fusion,
        block_message=_config["output_check"]["output_block_message"],
    )

    # Audit logger
    audit_cfg = _config["audit"]
    _audit_logger = AuditLogger(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # Statistics engine
    _stats_engine = StatisticsEngine(
        log_dir=str(project_root / audit_cfg["log_dir"]),
    )

    # LLM client (try to connect, non-fatal)
    llm_cfg = _config["llm"]
    try:
        _llm_client = LLMClient(LLMConfig(
            provider=llm_cfg["provider"],
            base_url=llm_cfg["base_url"],
            model=llm_cfg["model"],
            api_key=llm_cfg["api_key"],
            timeout=llm_cfg["timeout"],
            max_tokens=llm_cfg["max_tokens"],
        ))
        print(f"LLM 客户端已配置: {llm_cfg['provider']} / {llm_cfg['model']}")
    except Exception as e:
        print(f"LLM 客户端未配置（模拟模式）: {e}")
        _llm_client = None

    rule_count = sum(1 for _ in _rule_manager.get_enabled_rules())
    print(f"规则已加载: {rule_count} 条已启用")
    print("API 服务就绪 [OK]")


# =============================================================================
# POST /api/pipeline/check
# =============================================================================

@app.post("/api/pipeline/check", response_model=PipelineResult)
def pipeline_check(req: PipelineRequest):
    """Run the full content filtering pipeline on user input."""
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

    # Step 1: Normalize
    normalized = _normalizer.normalize(text)
    record.normalized_input = normalized.normalized

    # Step 2: Rule detection
    rule_evidence = _rule_detector.detect(normalized.normalized)

    # Step 3: Semantic detection
    semantic_evidence = _semantic_detector.detect(normalized.normalized)

    # Step 4: Risk fusion
    risk_result = _fusion.evaluate_input(rule_evidence, semantic_evidence)
    record.input_risk_level = risk_result.risk_level.value
    record.input_risk_category = (
        risk_result.risk_category.value if risk_result.risk_category else None
    )
    record.input_confidence = risk_result.confidence
    record.input_action = risk_result.action
    record.input_evidence = [
        {
            "source": e.source.value,
            "category": e.category.value if e.category else "",
            "confidence": e.confidence,
            "explanation": e.explanation,
        }
        for e in risk_result.evidence_chain
    ]

    # Step 5: Act on risk level
    if risk_result.risk_level == RiskLevel.HIGH:
        # Block directly
        record.final_output = "抱歉，您的请求包含不适宜内容，无法处理。"
        record.total_duration_ms = (time.time() - start_time) * 1000
        _audit_logger.log(record)
        return _build_pipeline_result(record)

    elif risk_result.risk_level == RiskLevel.MEDIUM:
        # Desensitize
        des_result = _desensitizer.desensitize(text, risk_result)
        safe_input = des_result.desensitized
        record.desensitized_input = safe_input
    else:
        safe_input = text

    # Step 6: Call LLM
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

    # Step 7: Output re-check
    output_result = _output_checker.check(llm_output)
    record.output_risk_level = (
        output_result.risk_result.risk_level.value
        if output_result.risk_result else "low"
    )
    record.output_passed = output_result.is_safe
    record.output_blocked = not output_result.is_safe
    record.final_output = output_result.final_output

    record.total_duration_ms = (time.time() - start_time) * 1000
    _audit_logger.log(record)
    return _build_pipeline_result(record)


def _build_pipeline_result(record: AuditRecord) -> PipelineResult:
    """Convert AuditRecord to PipelineResult response."""
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
                matchedPattern=ev.get("explanation", ""),
                matchedText="[已脱敏片段]",
                explanation=ev["explanation"],
            )
            for ev in record.input_evidence
        ],
    )


# =============================================================================
# GET /api/stats/overview
# =============================================================================

@app.get("/api/stats/overview", response_model=StatsOverview)
def stats_overview(days: int = 7):
    """Get aggregated statistics overview."""
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
# GET /api/rules
# =============================================================================

@app.get("/api/rules", response_model=list[RuleItem])
def list_rules(category: str | None = None):
    """Get all rules, optionally filtered by category."""
    assert _rule_manager is not None

    if category:
        try:
            cat_enum = RiskCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的风险类别: {category}")
        rules = _rule_manager.get_all_rules(cat_enum)
    else:
        rules = _rule_manager.get_all_rules()

    return [
        RuleItem(
            id=r.id,
            pattern=r.pattern,
            patternType=r.pattern_type,
            category=r.category.value,
            riskLevel=r.risk_level.value,
            enabled=r.enabled,
            description=r.description,
            source=r.source,
            updatedAt=r.updated_at,
        )
        for r in rules
    ]


# =============================================================================
# POST /api/feedback
# =============================================================================

@app.post("/api/feedback", response_model=FeedbackItem)
def submit_feedback(req: FeedbackRequest):
    """Submit misclassification feedback."""
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

    # Persist to feedback JSONL
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
# GET /api/audit
# =============================================================================

@app.get("/api/audit", response_model=list[dict])
def list_audit_logs(limit: int = 50):
    """Get recent audit log entries."""
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
                    records.append({
                        "requestId": entry.get("request_id", ""),
                        "timestamp": entry.get("timestamp", ""),
                        "action": inp.get("action", "pass"),
                        "riskLevel": inp.get("risk_level", "low"),
                        "category": inp.get("risk_category"),
                        "evidenceCount": inp.get("evidence_count", 0),
                        "llmCalled": llm.get("called", False),
                        "outputBlocked": out.get("blocked", False),
                        "durationMs": perf.get("total_duration_ms", 0),
                    })
                except json.JSONDecodeError:
                    continue

    # Return most recent first, limited
    records.reverse()
    return records[:limit]


# =============================================================================
# Health check
# =============================================================================

@app.get("/api/health")
def health():
    """Health check endpoint."""
    assert _rule_manager is not None
    return {
        "status": "ok",
        "rulesLoaded": sum(1 for _ in _rule_manager.get_enabled_rules()),
        "semanticAvailable": _semantic_detector.is_available if _semantic_detector else False,
        "llmAvailable": _llm_client is not None,
    }