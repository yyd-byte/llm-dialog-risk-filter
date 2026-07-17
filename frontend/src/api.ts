const API_BASE = "http://localhost:8000";

import type {
  AuditRecord,
  CategoryStat,
  DailyStat,
  FeedbackItem,
  PipelineResult,
  RuleMetadata,
  RuleMutationResponse,
  RulePage,
} from "./types";

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

export interface RuleFilters {
  page?: number;
  pageSize?: number;
  category?: string;
  source?: string;
  enabled?: boolean;
}

export async function fetchRules(filters: RuleFilters = {}): Promise<RulePage> {
  const params = new URLSearchParams();
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 50));
  if (filters.category) params.set("category", filters.category);
  if (filters.source) params.set("source", filters.source);
  if (filters.enabled !== undefined) params.set("enabled", String(filters.enabled));
  const response = await fetch(`${API_BASE}/api/rules?${params}`);
  if (!response.ok) throw new Error(`规则查询失败 (${response.status})`);
  return response.json();
}

export async function fetchRuleMetadata(): Promise<RuleMetadata> {
  const response = await fetch(`${API_BASE}/api/rules/metadata`);
  if (!response.ok) throw new Error(`规则元数据查询失败 (${response.status})`);
  return response.json();
}

export async function setRuleEnabled(
  ruleId: string,
  enabled: boolean,
  expectedVersion: string,
  token: string,
): Promise<RuleMutationResponse> {
  const response = await fetch(`${API_BASE}/api/rules/${encodeURIComponent(ruleId)}/enabled`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    body: JSON.stringify({ enabled, expectedVersion }),
  });
  if (!response.ok) throw new Error(`规则更新失败 (${response.status})`);
  return response.json();
}

export async function reloadRules(expectedVersion: string, token: string): Promise<RuleMetadata> {
  const response = await fetch(`${API_BASE}/api/rules/reload`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    body: JSON.stringify({ expectedVersion }),
  });
  if (!response.ok) throw new Error(`规则重载失败 (${response.status})`);
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