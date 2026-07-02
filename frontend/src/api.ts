const API_BASE = "http://localhost:8000";

import type { AuditRecord, CategoryStat, DailyStat, FeedbackItem, PipelineResult, RuleItem } from "./types";

// =============================================================================
// Pipeline
// =============================================================================

export async function runPipeline(input: string): Promise<PipelineResult> {
  const response = await fetch(`${API_BASE}/api/pipeline/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API 请求失败 (${response.status}): ${errorText}`);
  }

  return response.json();
}

// =============================================================================
// Statistics
// =============================================================================

export interface StatsOverview {
  totalRequests: number;
  blockRate: number;
  falsePositiveRate: number;
  totalLlmCalls: number;
  outputBlockRate: number;
  dailyStats: DailyStat[];
  categoryStats: CategoryStat[];
}

export async function fetchStats(days = 7): Promise<StatsOverview> {
  const response = await fetch(`${API_BASE}/api/stats/overview?days=${days}`);

  if (!response.ok) {
    throw new Error(`统计查询失败 (${response.status})`);
  }

  return response.json();
}

// =============================================================================
// Rules
// =============================================================================

export async function fetchRules(category?: string): Promise<RuleItem[]> {
  const url = category
    ? `${API_BASE}/api/rules?category=${category}`
    : `${API_BASE}/api/rules`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`规则查询失败 (${response.status})`);
  }

  return response.json();
}

// =============================================================================
// Audit logs
// =============================================================================

export async function fetchAuditLogs(limit = 50): Promise<AuditRecord[]> {
  const response = await fetch(`${API_BASE}/api/audit?limit=${limit}`);

  if (!response.ok) {
    throw new Error(`审计日志查询失败 (${response.status})`);
  }

  return response.json();
}

// =============================================================================
// Feedback
// =============================================================================

export async function submitFeedback(data: {
  type: string;
  requestId?: string;
  sample: string;
  suggestion: string;
  correctCategory?: string;
}): Promise<FeedbackItem> {
  const response = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`反馈提交失败 (${response.status})`);
  }

  return response.json();
}