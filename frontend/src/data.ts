import type {
  AuditRecord,
  CategoryStat,
  DailyStat,
  FeedbackItem,
  PipelineResult,
  RiskAction,
  RiskCategory,
  RiskLevel,
  RuleItem,
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

export const categoryStats: CategoryStat[] = [
  { category: "advertising", label: categoryLabels.advertising, count: 86, color: "#0f766e" },
  { category: "sensitive", label: categoryLabels.sensitive, count: 63, color: "#2563eb" },
  { category: "violent", label: categoryLabels.violent, count: 41, color: "#c2410c" },
  { category: "sexual", label: categoryLabels.sexual, count: 28, color: "#be123c" },
];

export const dailyStats: DailyStat[] = [
  { date: "06-26", blocked: 18, desensitized: 21, passed: 126, outputBlocked: 4 },
  { date: "06-27", blocked: 24, desensitized: 19, passed: 140, outputBlocked: 5 },
  { date: "06-28", blocked: 16, desensitized: 28, passed: 132, outputBlocked: 7 },
  { date: "06-29", blocked: 27, desensitized: 24, passed: 156, outputBlocked: 6 },
  { date: "06-30", blocked: 22, desensitized: 31, passed: 171, outputBlocked: 8 },
  { date: "07-01", blocked: 30, desensitized: 27, passed: 164, outputBlocked: 9 },
  { date: "07-02", blocked: 19, desensitized: 22, passed: 118, outputBlocked: 4 },
];

export const rules: RuleItem[] = [
  {
    id: "ADV-1024",
    pattern: "联系方式特征占位",
    patternType: "regex",
    category: "advertising",
    riskLevel: "high",
    enabled: true,
    description: "识别导流、联系方式、重复营销结构",
    source: "config/rules/advertising.yaml",
    updatedAt: "2026-07-01 20:14",
  },
  {
    id: "SEN-2008",
    pattern: "敏感话术占位",
    patternType: "keyword",
    category: "sensitive",
    riskLevel: "medium",
    enabled: true,
    description: "识别需要谨慎回复的边界表达",
    source: "config/rules/sensitive.yaml",
    updatedAt: "2026-07-01 19:42",
  },
  {
    id: "VIO-3017",
    pattern: "危险行为描述占位",
    patternType: "keyword",
    category: "violent",
    riskLevel: "high",
    enabled: true,
    description: "识别高风险危险行为或伤害意图",
    source: "config/rules/violent.yaml",
    updatedAt: "2026-06-30 22:10",
  },
  {
    id: "SEX-4188",
    pattern: "低俗表达占位",
    patternType: "keyword",
    category: "sexual",
    riskLevel: "high",
    enabled: false,
    description: "识别低俗或不适宜对话内容",
    source: "config/rules/sexual.yaml",
    updatedAt: "2026-06-29 17:36",
  },
];

export const auditRecords: AuditRecord[] = [
  {
    requestId: "8f4a92c1",
    timestamp: "2026-07-02 00:18:31",
    action: "pass",
    riskLevel: "low",
    evidenceCount: 0,
    llmCalled: true,
    outputBlocked: false,
    durationMs: 182,
  },
  {
    requestId: "a0c15e91",
    timestamp: "2026-07-02 00:16:08",
    action: "desensitize",
    riskLevel: "medium",
    category: "sensitive",
    evidenceCount: 2,
    llmCalled: true,
    outputBlocked: false,
    durationMs: 244,
  },
  {
    requestId: "fe91ab3d",
    timestamp: "2026-07-02 00:14:47",
    action: "block",
    riskLevel: "high",
    category: "advertising",
    evidenceCount: 4,
    llmCalled: false,
    outputBlocked: false,
    durationMs: 63,
  },
  {
    requestId: "70e8dc55",
    timestamp: "2026-07-02 00:12:02",
    action: "pass",
    riskLevel: "low",
    evidenceCount: 0,
    llmCalled: true,
    outputBlocked: true,
    durationMs: 296,
  },
];

export const feedbackItems: FeedbackItem[] = [
  {
    id: "FB-001",
    timestamp: "2026-07-01 22:31",
    type: "false_positive",
    status: "pending",
    sample: "新闻科普语境被识别为高风险",
    suggestion: "增加上下文白名单与语义置信度阈值",
  },
  {
    id: "FB-002",
    timestamp: "2026-07-01 21:58",
    type: "wrong_category",
    status: "reviewed",
    sample: "边界客服投诉话术分类不准确",
    suggestion: "调整敏感话术与广告引流规则优先级",
  },
  {
    id: "FB-003",
    timestamp: "2026-06-30 23:11",
    type: "false_negative",
    status: "resolved",
    sample: "混淆变体样本未触发规则召回",
    suggestion: "补充文本规范化与正则变体",
  },
];

export const defaultResult: PipelineResult = {
  requestId: "demo-0001",
  timestamp: "2026-07-02 00:20:00",
  originalInput: "请帮我写一段客服欢迎语，语气自然一点。",
  normalizedInput: "请帮我写一段客服欢迎语，语气自然一点。",
  riskLevel: "low",
  confidence: 0.08,
  action: "pass",
  desensitizedInput: "请帮我写一段客服欢迎语，语气自然一点。",
  llmCalled: true,
  llmOutput: "您好，欢迎咨询。请问有什么可以帮您处理？",
  outputRiskLevel: "low",
  outputBlocked: false,
  finalOutput: "您好，欢迎咨询。请问有什么可以帮您处理？",
  durationMs: 188,
  evidenceChain: [],
};
