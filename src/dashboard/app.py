"""Streamlit dashboard for content moderation operations."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from src.audit.statistics import StatisticsEngine


def main():
    """Main dashboard entry point."""
    st.set_page_config(
        page_title="内容风控运营看板",
        page_icon="🛡️",
        layout="wide",
    )

    st.title("🛡️ 大模型对话内容风控运营看板")
    st.markdown("实时监控内容风控系统的运行状态与拦截效果")

    stats_engine = StatisticsEngine()

    # ---- Sidebar ----
    st.sidebar.header("⚙️ 筛选条件")
    days = st.sidebar.slider("统计天数", 1, 30, 7)
    st.sidebar.markdown("---")
    st.sidebar.info("数据来源: `data/logs/audit-*.jsonl`")

    overview = stats_engine.get_overview(days=days)

    # ---- Key Metrics Row ----
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📊 总请求数", overview.total_requests)
    with col2:
        st.metric("🛑 明显违规拦截率", f"{overview.block_rate:.1%}")
    with col3:
        st.metric("⚠️ 正常文本误判率", f"{overview.false_positive_rate:.1%}")
    with col4:
        st.metric("🤖 LLM 调用次数", overview.total_llm_calls)
    with col5:
        st.metric("🔁 输出复检拦截率", f"{overview.output_block_rate:.1%}")

    # ---- Daily Trend ----
    st.header("📈 每日请求趋势")
    if overview.daily_stats:
        daily_data = []
        for ds in overview.daily_stats:
            daily_data.append({
                "日期": ds.date,
                "拦截": ds.input_blocked,
                "脱敏": ds.input_desensitized,
                "放行": ds.input_passed,
            })
        st.bar_chart(daily_data, x="日期", y=["拦截", "脱敏", "放行"])
    else:
        st.info("暂无数据。系统运行后将自动生成统计。")

    # ---- Category Breakdown ----
    col_left, col_right = st.columns(2)
    with col_left:
        st.header("🏷️ 违规类型占比")
        if overview.top_categories:
            cat_data = {
                "类别": [c[0] for c in overview.top_categories],
                "数量": [c[1] for c in overview.top_categories],
            }
            st.bar_chart(cat_data, x="类别", y="数量")
        else:
            st.info("暂无违规数据")

    with col_right:
        st.header("📋 拦截/脱敏/放行分布")
        if overview.total_requests > 0:
            st.write("待数据积累后展示分布饼图")
        else:
            st.info("暂无数据")

    # ---- Footer ----
    st.markdown("---")
    st.caption("LLM Dialog Risk Filter v0.1.0 | 全国人工智能竞赛")


if __name__ == "__main__":
    main()