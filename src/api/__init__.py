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