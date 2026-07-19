"""流水线检测端点 — 内容风控的核心 API。"""

import time
import uuid

from fastapi import APIRouter

from src.api.bootstrap import AppComponents
from src.api.models import PipelineRequest, PipelineResult, EvidenceItem
from src.audit.logger import AuditRecord
from src.decision.models import RiskLevel

router = APIRouter()


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


@router.post("/api/pipeline/check", response_model=PipelineResult)
def pipeline_check(req: PipelineRequest):
    """执行完整的内容过滤流水线。

    流水线步骤：
    1. 文本规范化 → 2. 规则检测 → 3. 语义检测 → 4. 风险融合
    → 5. 分级处置（拦截/脱敏/放行）→ 6. LLM 调用 → 7. 输出复检

    Args:
        req: 包含用户输入文本的请求体。

    Returns:
        PipelineResult: 包含全链路信息的检测结果。
    """
    components = AppComponents.get()
    _normalizer = components.normalizer
    _rule_detector = components.rule_detector
    _semantic_detector = components.semantic_detector
    _fusion = components.fusion
    _desensitizer = components.desensitizer
    _output_checker = components.output_checker
    _audit_logger = components.audit_logger
    _llm_client = components.llm_client

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
