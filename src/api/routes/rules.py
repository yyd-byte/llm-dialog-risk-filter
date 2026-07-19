"""规则管理端点 — 规则的查询、启用/禁用、重载。"""

import secrets

from fastapi import APIRouter, Header, HTTPException, Query

from src.api.bootstrap import AppComponents
from src.api.models import (
    RuleItem,
    RulePage,
    RuleMetadata,
    RuleMutationResponse,
    RuleSourceSummary,
    SetRuleEnabledRequest,
    ReloadRequest,
)
from src.decision.models import RiskCategory
from src.rules.manager import RuleVersionConflictError

router = APIRouter()


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
    components = AppComponents.get()
    _rule_manager = components.rule_manager
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
    """拒绝未提供有效管理令牌的规则管理写操作。"""
    components = AppComponents.get()
    if not components.rules_admin_token:
        raise HTTPException(status_code=503, detail="规则管理功能不可用")
    if x_admin_token is None or not secrets.compare_digest(
        x_admin_token, components.rules_admin_token
    ):
        raise HTTPException(status_code=401, detail="未授权")


# =============================================================================
# 规则管理端点
# =============================================================================


@router.get("/api/rules", response_model=RulePage)
def list_rules(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
    category: str | None = Query(default=None, description="风险类别筛选"),
    source: str | None = Query(default=None, description="来源筛选"),
    enabled: bool | None = Query(default=None, description="启用状态筛选"),
):
    """获取规则的分页过滤列表。"""
    components = AppComponents.get()
    _rule_manager = components.rule_manager
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


@router.get("/api/rules/metadata", response_model=RuleMetadata)
def rule_metadata():
    """获取当前规则集的版本号和来源摘要。"""
    return _rule_metadata()


@router.patch("/api/rules/{rule_id}/enabled", response_model=RuleMutationResponse)
def set_rule_enabled(
    rule_id: str,
    request: SetRuleEnabledRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """持久化规则的启用状态并立即重建检测缓存。"""
    _require_rules_admin_token(x_admin_token)
    components = AppComponents.get()
    _rule_manager = components.rule_manager
    _rule_detector = components.rule_detector
    _rule_management_audit = components.rule_management_audit
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


@router.post("/api/rules/reload", response_model=RuleMetadata)
def reload_rules(
    request: ReloadRequest,
    _: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """重新加载 YAML 规则并重建检测缓存，无需重启 API。"""
    _require_rules_admin_token(_)
    components = AppComponents.get()
    _rule_manager = components.rule_manager
    _rule_detector = components.rule_detector
    _rule_management_audit = components.rule_management_audit
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
