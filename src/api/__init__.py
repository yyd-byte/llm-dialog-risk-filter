"""API 服务模块 — FastAPI RESTful 接口。

提供流水线检测、统计查询、规则管理、反馈提交和审计日志等端点。
通过延迟导入避免循环依赖。
"""

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

__all__ = [
    "PipelineRequest",
    "PipelineResult",
    "EvidenceItem",
    "StatsOverview",
    "DailyStatItem",
    "CategoryStatItem",
    "RuleItem",
    "FeedbackRequest",
    "FeedbackItem",
    "app",
]


def __getattr__(name):
    """Lazy-import app so models can be used without fastapi installed."""
    if name == "app":
        from src.api.server import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")