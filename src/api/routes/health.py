"""健康检查端点。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health():
    """返回服务健康状态。

    Returns:
        包含服务状态、已加载规则数和模型可用性的字典。
    """
    from src.api.bootstrap import AppComponents

    components = AppComponents.get()
    return {
        "status": "ok",
        "rulesLoaded": sum(1 for _ in components.rule_manager.get_enabled_rules()),
        "semanticAvailable": (
            components.semantic_detector.is_available if components.semantic_detector else False
        ),
        "llmAvailable": components.llm_client is not None,
    }
