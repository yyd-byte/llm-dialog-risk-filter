"""统计查询端点。"""

from fastapi import APIRouter, Query

from src.api.bootstrap import AppComponents
from src.api.models import StatsOverview, DailyStatItem, CategoryStatItem

router = APIRouter()

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


@router.get("/api/stats/overview", response_model=StatsOverview)
def stats_overview(days: int = Query(default=7, description="统计最近 N 天")):
    """获取聚合统计概览。

    Args:
        days: 统计的天数范围，默认 7 天。

    Returns:
        包含概览指标、每日趋势和类别分布的 StatsOverview。
    """
    components = AppComponents.get()
    _stats_engine = components.stats_engine

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
