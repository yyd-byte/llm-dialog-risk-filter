import type {
  PipelineResult,
  RiskAction,
  RiskCategory,
  RiskLevel,
} from "./types";

export const categoryLabels: Record<RiskCategory, string> = {
  sexual: "色情低俗",
  violent: "暴力危险",
  advertising: "广告引流",
  sensitive: "敏感话术",
};

export const riskLevelLabels: Record<RiskLevel, string> = {
  high: "高风险",
  medium: "中风险",
  low: "正常",
};

export const actionLabels: Record<RiskAction, string> = {
  block: "拦截",
  desensitize: "脱敏放行",
  pass: "直接放行",
};

export const defaultResult: PipelineResult = {
  requestId: "——",
  timestamp: "——",
  originalInput: "",
  normalizedInput: "",
  riskLevel: "low",
  confidence: 0,
  action: "pass",
  desensitizedInput: "",
  llmCalled: false,
  llmOutput: "",
  outputRiskLevel: "low",
  outputBlocked: false,
  finalOutput: "",
  durationMs: 0,
  evidenceChain: [],
};