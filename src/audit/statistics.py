"""统计引擎 — 将审计日志聚合为看板可用的统计数据。"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class DailyStats:
    """单日的聚合统计数据。"""

    date: str
    total_requests: int = 0
    # 输入侧
    input_blocked: int = 0       # HIGH 风险 → 拦截
    input_desensitized: int = 0  # MEDIUM 风险 → 脱敏
    input_passed: int = 0        # LOW 风险 → 放行
    # 类别分布
    category_counts: dict[str, int] = field(default_factory=dict)
    # 输出侧
    output_checked: int = 0
    output_blocked: int = 0
    # LLM
    llm_calls: int = 0
    # 性能
    avg_duration_ms: float = 0.0


@dataclass
class StatsOverview:
    """高层级统计概览。"""

    total_requests: int = 0
    block_rate: float = 0.0
    false_positive_rate: float = 0.0
    total_llm_calls: int = 0
    output_block_rate: float = 0.0
    top_categories: list[tuple[str, int]] = field(default_factory=list)
    daily_stats: list[DailyStats] = field(default_factory=list)


class StatisticsEngine:
    """将审计日志数据聚合并生成供看板显示的统计信息。"""

    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)

    def load_daily_stats(self, days: int = 7) -> list[DailyStats]:
        """加载最近 N 天的聚合日统计。"""
        daily_map: dict[str, DailyStats] = {}

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_map[date] = DailyStats(date=date)

        log_files = sorted(self.log_dir.glob("audit-*.jsonl"))
        for log_file in log_files:
            self._process_log_file(log_file, daily_map)

        return sorted(daily_map.values(), key=lambda d: d.date)

    def get_overview(self, days: int = 7) -> StatsOverview:
        """获取高层级统计概览。"""
        daily_stats = self.load_daily_stats(days)
        overview = StatsOverview(daily_stats=daily_stats)

        for ds in daily_stats:
            overview.total_requests += ds.total_requests
            overview.total_llm_calls += ds.llm_calls
            overview.output_block_rate += ds.output_blocked

        if overview.total_requests > 0:
            overview.block_rate = sum(
                ds.input_blocked for ds in daily_stats
            ) / overview.total_requests
            overview.false_positive_rate = 0.0  # Requires feedback data

        # 聚合各类别计数
        cat_counter: Counter = Counter()
        for ds in daily_stats:
            for cat, count in ds.category_counts.items():
                cat_counter[cat] += count
        overview.top_categories = cat_counter.most_common(5)

        return overview

    def _process_log_file(self, filepath: Path,
                          daily_map: dict[str, DailyStats]) -> None:
        """处理单个 JSONL 日志文件并聚合成日统计数据。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)  # 解析 JSON 行
                    except json.JSONDecodeError:
                        continue  # 跳过损坏的行

                    ts = record.get("timestamp", "")
                    date = ts[:10] if ts else ""  # 取日期部分（YYYY-MM-DD）
                    if date not in daily_map:
                        continue

                    ds = daily_map[date]
                    ds.total_requests += 1

                    # 按输入动作分类统计
                    inp = record.get("input", {})
                    action = inp.get("action", "pass")
                    if action == "block":
                        ds.input_blocked += 1
                    elif action == "desensitize":
                        ds.input_desensitized += 1
                    else:
                        ds.input_passed += 1

                    # 按风险类别统计
                    cat = inp.get("risk_category", "")
                    if cat:
                        ds.category_counts[cat] = ds.category_counts.get(cat, 0) + 1

                    # LLM 调用统计
                    llm = record.get("llm", {})
                    if llm.get("called"):
                        ds.llm_calls += 1

                    # 输出复检统计
                    out = record.get("output", {})
                    if out.get("checked"):
                        ds.output_checked += 1
                    if out.get("blocked"):
                        ds.output_blocked += 1

        except Exception:
            pass  # 跳过损坏的日志文件