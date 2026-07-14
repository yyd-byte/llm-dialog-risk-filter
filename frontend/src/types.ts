export type RiskLevel = "high" | "medium" | "low";
export type RiskCategory = "sexual" | "violent" | "advertising" | "sensitive";
export type DetectionSource = "rule" | "semantic";
export type RiskAction = "block" | "desensitize" | "pass";

export interface Evidence {
  source: DetectionSource;
  category: RiskCategory;
  confidence: number;
  matchedPattern: string;
  matchedText: string;
  explanation: string;
  step: string;           // normalize | rule | semantic | fusion | desensitize
  metadata?: Record<string, unknown>;
}

export interface PipelineResult {
  requestId: string;
  timestamp: string;
  originalInput: string;
  normalizedInput: string;
  riskLevel: RiskLevel;
  riskCategory?: RiskCategory;
  confidence: number;
  action: RiskAction;
  desensitizedInput: string;
  llmCalled: boolean;
  llmOutput: string;
  outputRiskLevel: RiskLevel;
  outputBlocked: boolean;
  finalOutput: string;
  durationMs: number;
  evidenceChain: Evidence[];
}

export interface DailyStat {
  date: string;
  blocked: number;
  desensitized: number;
  passed: number;
  outputBlocked: number;
}

export interface CategoryStat {
  category: RiskCategory;
  label: string;
  count: number;
  color: string;
}

export interface RuleItem {
  id: string;
  pattern: string;
  patternType: "keyword" | "regex";
  category: RiskCategory;
  riskLevel: RiskLevel;
  enabled: boolean;
  description: string;
  source: string;
  updatedAt: string;
}

export interface AuditRecord {
  requestId: string;
  timestamp: string;
  action: RiskAction;
  riskLevel: RiskLevel;
  category?: RiskCategory;
  evidenceCount: number;
  llmCalled: boolean;
  outputBlocked: boolean;
  durationMs: number;
}

export interface FeedbackItem {
  id: string;
  timestamp: string;
  type: "false_positive" | "false_negative" | "wrong_category";
  status: "pending" | "reviewed" | "resolved";
  sample: string;
  suggestion: string;
}
