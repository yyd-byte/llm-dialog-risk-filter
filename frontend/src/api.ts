import { defaultResult } from "./data";
import type { Evidence, PipelineResult, RiskCategory, RiskLevel } from "./types";

const categoryHints: Array<{ category: RiskCategory; hints: string[] }> = [
  { category: "advertising", hints: ["联系方式", "引流", "广告", "私信", "购买"] },
  { category: "sensitive", hints: ["敏感", "投诉", "边界", "政策", "账号"] },
  { category: "violent", hints: ["危险", "伤害", "攻击", "暴力"] },
  { category: "sexual", hints: ["低俗", "成人", "不适宜"] },
];

const highRiskHints = ["高风险", "违规", "绕过", "危险", "导流", "明显"];
const mediumRiskHints = ["疑似", "边界", "敏感", "联系方式", "投诉"];

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function inferCategory(text: string): RiskCategory | undefined {
  const matched = categoryHints.find((item) => item.hints.some((hint) => text.includes(hint)))?.category;
  if (matched) {
    return matched;
  }
  if (text.includes("高风险") || text.includes("违规")) {
    return "sensitive";
  }
  return undefined;
}

function inferRiskLevel(text: string): RiskLevel {
  if (highRiskHints.some((hint) => text.includes(hint))) {
    return "high";
  }
  if (mediumRiskHints.some((hint) => text.includes(hint))) {
    return "medium";
  }
  return "low";
}

function buildEvidence(category: RiskCategory | undefined, riskLevel: RiskLevel): Evidence[] {
  if (!category || riskLevel === "low") {
    return [];
  }

  const confidence = riskLevel === "high" ? 0.91 : 0.66;
  return [
    {
      source: "rule",
      category,
      confidence,
      matchedPattern: `${category}-占位规则`,
      matchedText: "[已脱敏片段]",
      explanation: "规则层召回到风险表达，已隐藏原始命中内容。",
    },
    {
      source: "semantic",
      category,
      confidence: Math.max(0.54, confidence - 0.17),
      matchedPattern: "semantic-classifier-placeholder",
      matchedText: "[语义上下文]",
      explanation: "语义层给出二次确认结果，等待后端模型接入。",
    },
  ];
}

function desensitize(text: string, riskLevel: RiskLevel, category?: RiskCategory) {
  if (riskLevel !== "medium") {
    return text;
  }
  const label = category ? `${category}-risk-fragment` : "risk-fragment";
  return text.replace(/联系方式|敏感|边界|投诉|疑似/g, `[${label}]`);
}

export async function runPipeline(input: string): Promise<PipelineResult> {
  await wait(520);

  const trimmed = input.trim();
  if (!trimmed) {
    return defaultResult;
  }

  const normalizedInput = trimmed.replace(/\s+/g, " ");
  const riskLevel = inferRiskLevel(normalizedInput);
  const riskCategory = inferCategory(normalizedInput);
  const action = riskLevel === "high" ? "block" : riskLevel === "medium" ? "desensitize" : "pass";
  const llmCalled = action !== "block";
  const outputBlocked = normalizedInput.includes("输出复检");
  const safeReply = "已根据合规策略生成安全回复，并记录本次审计链路。";

  return {
    requestId: Math.random().toString(16).slice(2, 10),
    timestamp: new Date().toLocaleString("zh-CN", { hour12: false }),
    originalInput: trimmed,
    normalizedInput,
    riskLevel,
    riskCategory,
    confidence: riskLevel === "high" ? 0.93 : riskLevel === "medium" ? 0.68 : 0.09,
    action,
    desensitizedInput: action === "desensitize" ? desensitize(normalizedInput, riskLevel, riskCategory) : normalizedInput,
    llmCalled,
    llmOutput: llmCalled ? "后端大模型回复占位：这里将展示真实模型生成内容。" : "",
    outputRiskLevel: outputBlocked ? "high" : "low",
    outputBlocked,
    finalOutput:
      action === "block"
        ? "很抱歉，该请求存在较高风险，系统已拦截并提供合规提示。"
        : outputBlocked
          ? "模型输出未通过安全复检，已替换为标准合规提示。"
          : safeReply,
    durationMs: Math.floor(120 + Math.random() * 220),
    evidenceChain: buildEvidence(riskCategory, riskLevel),
  };
}
