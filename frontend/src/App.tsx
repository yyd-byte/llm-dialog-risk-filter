import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  FileText,
  Gauge,
  History,
  MessageSquareText,
  Play,
  RefreshCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  ShieldX,
  SlidersHorizontal,
  Sparkles,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchAuditLogs, fetchRuleMetadata, fetchRules, fetchStats, reloadRules, runPipeline, setRuleEnabled, submitFeedback } from "./api";
import {
  actionLabels,
  categoryLabels,
  defaultResult,
  riskLevelLabels,
  stepLabels,
  stepIcons,
} from "./data";
import type {
  AuditRecord,
  CategoryStat,
  DailyStat,
  PipelineResult,
  RiskAction,
  RiskLevel,
  RuleItem,
  RuleMetadata,
} from "./types";

type View = "console" | "dashboard" | "rules" | "audit" | "feedback";

const navItems: Array<{ id: View; label: string; icon: typeof MessageSquareText }> = [
  { id: "console", label: "链路演示", icon: MessageSquareText },
  { id: "dashboard", label: "运营看板", icon: BarChart3 },
  { id: "rules", label: "规则中心", icon: Settings2 },
  { id: "audit", label: "审计日志", icon: History },
  { id: "feedback", label: "误判反馈", icon: ClipboardList },
];

const examples = [
  "请帮我写一段客服欢迎语，语气自然一点。",
  "今天天气真好，适合出去散步。",
  "加我微信abc123456了解详情",
  "美女裸聊一对一私密直播",
  "我知道你家地址，再惹我杀了你全家",
];

function App() {
  const [view, setView] = useState<View>("console");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck size={24} />
          </span>
          <div>
            <strong>内容风控网关</strong>
            <span>LLM Dialog Risk Filter</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={view === item.id ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => setView(item.id)}
                title={item.label}
                type="button"
              >
                <Icon size={19} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="backend-card">
          <span className="status-dot" />
          <div>
            <strong>后端已连接</strong>
            <span>API: localhost:8000</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <Topbar />
        {view === "console" && <ConsoleView />}
        {view === "dashboard" && <DashboardView />}
        {view === "rules" && <RulesView />}
        {view === "audit" && <AuditView />}
        {view === "feedback" && <FeedbackView />}
      </main>
    </div>
  );
}

function Topbar() {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">输入拦截 + 后置复检 + 可解释审计</p>
        <h1>面向对话场景的大模型输入输出违规内容过滤系统</h1>
      </div>
      <div className="topbar-actions">
        <button className="icon-button" title="刷新数据" type="button" onClick={() => window.location.reload()}>
          <RefreshCcw size={18} />
        </button>
        <button className="icon-button" title="导出审计摘要" type="button">
          <Download size={18} />
        </button>
      </div>
    </header>
  );
}

function ConsoleView() {
  const [input, setInput] = useState(examples[0]);
  const [result, setResult] = useState<PipelineResult>(defaultResult);
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    setLoading(true);
    try {
      const next = await runPipeline(input);
      setResult(next);
    } catch (err) {
      setResult({ ...defaultResult, originalInput: input, finalOutput: `请求失败: ${err}` });
    }
    setLoading(false);
  }

  return (
    <section className="view-stack">
      <div className="console-grid">
        <section className="panel input-panel">
          <PanelHeader icon={Send} title="输入检测台" meta="POST /api/pipeline/check" />
          <textarea
            aria-label="待检测输入"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="输入一段对话内容"
          />
          <div className="example-row">
            {examples.map((item) => (
              <button key={item} type="button" onClick={() => setInput(item)}>
                {item.length > 18 ? `${item.slice(0, 18)}...` : item}
              </button>
            ))}
          </div>
          <div className="control-row">
            <label className="segmented-control">
              <span>模式</span>
              <select defaultValue="full">
                <option value="full">完整链路</option>
                <option value="input">仅输入侧</option>
                <option value="output">仅输出复检</option>
              </select>
            </label>
            <button className="primary-button" onClick={handleRun} disabled={loading} type="button">
              {loading ? <Activity size={18} /> : <Play size={18} />}
              <span>{loading ? "检测中" : "运行检测"}</span>
            </button>
          </div>
        </section>

        <section className="panel result-panel">
          <PanelHeader icon={ShieldCheck} title="处置结果" meta={result.requestId} />
          <div className="result-summary">
            <RiskBadge level={result.riskLevel} />
            <div>
              <strong>{actionLabels[result.action]}</strong>
              <span>{result.riskCategory ? categoryLabels[result.riskCategory] : "未发现风险类别"}</span>
            </div>
            <div className="confidence-ring" style={{ "--value": `${result.confidence * 100}%` } as React.CSSProperties}>
              <span>{Math.round(result.confidence * 100)}</span>
            </div>
          </div>

          <div className="pipeline">
            <PipelineStep label="规范化" active done />
            <PipelineStep label="规则召回" active={result.evidenceChain.some((item) => item.source === "rule")} done />
            <PipelineStep label="语义判断" active={result.evidenceChain.some((item) => item.source === "semantic")} done />
            <PipelineStep label="风险融合" active done />
            <PipelineStep label="输出复检" active={result.llmCalled} done={!result.outputBlocked} warning={result.outputBlocked} />
          </div>

          <div className="result-blocks">
            <TextBlock title="规范化输入" text={result.normalizedInput} />
            <TextBlock title="脱敏后输入" text={result.desensitizedInput || "未触发脱敏"} />
            <TextBlock title="最终返回" text={result.finalOutput} emphasized />
          </div>
        </section>
      </div>

      <section className="panel">
        <PanelHeader icon={FileText} title="可解释证据链" meta={`${result.durationMs} ms`} />
        <div className="evidence-timeline">
          {result.evidenceChain.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="暂无风险证据" text="本次输入按低风险链路放行，已生成审计记录。" />
          ) : (
            result.evidenceChain.map((item, index) => (
              <div className="evidence-step" key={`${item.step}-${index}`}>
                <div className="step-indicator">
                  <span className={`step-dot step-${item.step} ${item.confidence > 0 ? "hit" : ""}`}>
                    {stepIcons[item.step] || "○"}
                  </span>
                  {index < result.evidenceChain.length - 1 && <span className="step-line" />}
                </div>
                <div className={`step-body ${item.confidence > 0 ? "has-hit" : ""}`}>
                  <div className="step-header">
                    <span className={`step-badge badge-${item.step}`}>
                      {stepLabels[item.step] || item.step}
                    </span>
                    <span className={`category-tag cat-${item.category}`}>
                      {categoryLabels[item.category] || item.category}
                    </span>
                    {item.confidence > 0 && (
                      <span className="confidence-badge">
                        {Math.round(item.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  <p className="step-explain">{item.explanation}</p>
                  <div className="step-detail">
                    {item.matchedPattern && (
                      <span className="detail-chip" title="命中模式">
                        📋 {item.matchedPattern.length > 60
                          ? item.matchedPattern.slice(0, 60) + "..."
                          : item.matchedPattern}
                      </span>
                    )}
                    {item.matchedText && (
                      <span className="detail-chip" title="命中原文">
                        📝 &ldquo;{item.matchedText.length > 40
                          ? item.matchedText.slice(0, 40) + "..."
                          : item.matchedText}&rdquo;
                      </span>
                    )}
                    {item.metadata && item.metadata.rule_count !== undefined && (
                      <span className="detail-chip">
                        📊 规则{String(item.metadata.rule_count)}条 + 语义{String(item.metadata.semantic_count)}条
                      </span>
                    )}
                    {item.metadata && Array.isArray(item.metadata.changes) && (item.metadata.changes as string[]).length > 0 && (
                      <span className="detail-chip">
                        🔧 {(item.metadata.changes as string[]).join(" · ")}
                      </span>
                    )}
                    {item.metadata && item.metadata.original_fragment !== undefined && (
                      <span className="detail-chip">
                        🔒 &ldquo;{String(item.metadata.original_fragment)}&rdquo; → &ldquo;{String(item.metadata.replacement)}&rdquo;
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </section>
  );
}

function DashboardView() {
  const [stats, setStats] = useState<{
    totalRequests: number;
    blockRate: number;
    falsePositiveRate: number;
    totalLlmCalls: number;
    outputBlockRate: number;
    dailyStats: DailyStat[];
    categoryStats: CategoryStat[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats(7)
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <section className="view-stack"><div className="panel"><p style={{ padding: 40, textAlign: "center" }}>加载中...</p></div></section>;
  }

  if (!stats) {
    return <section className="view-stack"><div className="panel"><p style={{ padding: 40, textAlign: "center" }}>数据加载失败，请确认后端已启动</p></div></section>;
  }

  const totals = {
    total: stats.totalRequests,
    blocked: stats.dailyStats.reduce((sum, d) => sum + d.blocked, 0),
    outputBlocked: stats.dailyStats.reduce((sum, d) => sum + d.outputBlocked, 0),
    desensitized: stats.dailyStats.reduce((sum, d) => sum + d.desensitized, 0),
  };

  return (
    <section className="view-stack">
      <div className="metric-grid">
        <MetricCard icon={Gauge} label="总请求数" value={totals.total.toLocaleString()} trend="" />
        <MetricCard icon={ShieldX} label="拦截率" value={`${(stats.blockRate * 100).toFixed(1)}%`} trend="" danger />
        <MetricCard icon={Sparkles} label="脱敏放行" value={totals.desensitized.toString()} trend="" />
        <MetricCard icon={AlertTriangle} label="输出复检拦截" value={totals.outputBlocked.toString()} trend="" warning />
      </div>

      <div className="dashboard-grid">
        <section className="panel trend-panel">
          <PanelHeader icon={BarChart3} title="每日请求趋势" meta="最近 7 天" />
          <div className="stacked-chart">
            {stats.dailyStats.map((day) => {
              const total = day.blocked + day.desensitized + day.passed;
              if (total === 0) {
                return (
                  <div className="chart-row" key={day.date}>
                    <span>{day.date.slice(5)}</span>
                    <div className="chart-track"><i className="passed" style={{ width: "100%" }} /></div>
                    <strong>0</strong>
                  </div>
                );
              }
              return (
                <div className="chart-row" key={day.date}>
                  <span>{day.date.slice(5)}</span>
                  <div className="chart-track">
                    <i className="passed" style={{ width: `${(day.passed / total) * 100}%` }} />
                    <i className="desensitized" style={{ width: `${(day.desensitized / total) * 100}%` }} />
                    <i className="blocked" style={{ width: `${(day.blocked / total) * 100}%` }} />
                  </div>
                  <strong>{total}</strong>
                </div>
              );
            })}
          </div>
          <ChartLegend />
        </section>

        <section className="panel category-panel">
          <PanelHeader icon={SlidersHorizontal} title="违规类型占比" meta="四类知识体系" />
          <div className="category-list">
            {stats.categoryStats.length === 0 ? (
              <p style={{ padding: 20, textAlign: "center", color: "#94a3b8" }}>暂无数据</p>
            ) : (
              stats.categoryStats.map((item) => (
                <div className="category-row" key={item.category}>
                  <span className="category-swatch" style={{ backgroundColor: item.color }} />
                  <span>{item.label}</span>
                  <div className="mini-track">
                    <i style={{ width: `${Math.min(item.count, 100)}%`, backgroundColor: item.color }} />
                  </div>
                  <strong>{item.count}</strong>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function RulesView() {
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [metadata, setMetadata] = useState<RuleMetadata | null>(null);
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [enabled, setEnabled] = useState("");
  const [page, setPage] = useState(1);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyRule, setBusyRule] = useState("");
  const [message, setMessage] = useState("");

  async function loadRules(nextPage = page) {
    setLoading(true);
    try {
      const enabledFilter = enabled === "" ? undefined : enabled === "true";
      const [rulePage, nextMetadata] = await Promise.all([
        fetchRules({ page: nextPage, category, source, enabled: enabledFilter }),
        fetchRuleMetadata(),
      ]);
      setRules(rulePage.items);
      setMetadata(nextMetadata);
      setPage(rulePage.page);
    } catch {
      setMessage("规则数据加载失败，请确认后端服务可用。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadRules(1); }, [category, source, enabled]);

  async function handleEnabledChange(rule: RuleItem) {
    if (!metadata || !token) return;
    setBusyRule(rule.id);
    setMessage("");
    try {
      await setRuleEnabled(rule.id, !rule.enabled, metadata.version, token);
      await loadRules(page);
      setMessage("规则状态已更新并生效。");
    } catch {
      setMessage("规则更新失败，请检查管理员令牌或刷新后重试。");
    } finally {
      setBusyRule("");
    }
  }

  async function handleReload() {
    if (!metadata || !token || !window.confirm("确认从本地 YAML 重新加载规则吗？")) return;
    setMessage("");
    try {
      const nextMetadata = await reloadRules(metadata.version, token);
      setMetadata(nextMetadata);
      await loadRules(1);
      setMessage("规则已重新加载并重建检测索引。");
    } catch {
      setMessage("规则重载失败，请检查管理员令牌或 YAML 文件。");
    }
  }

  if (loading && !metadata) {
    return <section className="panel"><p style={{ padding: 40, textAlign: "center" }}>加载中...</p></section>;
  }

  const totalPages = Math.max(1, Math.ceil((metadata?.total ?? 0) / 50));
  return (
    <section className="panel">
      <PanelHeader icon={Database} title="规则词库管理" meta={`${metadata?.enabledTotal ?? 0} / ${metadata?.total ?? 0} 条启用 · ${metadata?.version.slice(0, 20) ?? ""}`} />
      <div className="table-toolbar">
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">全部类别</option>
          {Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="">全部来源</option>
          {metadata?.sources.map((item) => <option key={item.source || "manual"} value={item.source}>{item.source || "手工规则"}</option>)}
        </select>
        <select value={enabled} onChange={(event) => setEnabled(event.target.value)}>
          <option value="">全部状态</option><option value="true">已启用</option><option value="false">已停用</option>
        </select>
        <input type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="管理员令牌" aria-label="管理员令牌" />
        <button className="secondary-button" type="button" disabled={!token} onClick={handleReload}>
          <RefreshCcw size={17} /><span>重新加载规则</span>
        </button>
      </div>
      {message && <p style={{ padding: "0 20px", color: message.includes("失败") ? "#dc2626" : "#16a34a" }}>{message}</p>}
      <div className="data-table">
        <div className="table-head rules-head"><span>状态</span><span>规则</span><span>类别</span><span>等级</span><span>来源</span><span>更新</span></div>
        {rules.map((rule) => (
          <div className="table-row rules-row" key={rule.id}>
            <button className="toggle-state" type="button" disabled={!token || busyRule === rule.id} onClick={() => void handleEnabledChange(rule)} aria-label={`${rule.enabled ? "停用" : "启用"}规则 ${rule.id}`}>
              {rule.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
            </button>
            <div><strong>{rule.id}</strong><span>{rule.pattern}</span><small>{rule.description}</small></div>
            <span>{categoryLabels[rule.category]}</span><RiskBadge level={rule.riskLevel} compact />
            <span className="mono">{rule.source || "手工规则"}</span><span>{rule.updatedAt || "未记录"}</span>
          </div>
        ))}
      </div>
      <div className="table-toolbar" style={{ justifyContent: "space-between" }}>
        <span>第 {page} / {totalPages} 页</span>
        <div><button className="secondary-button" type="button" disabled={page <= 1 || loading} onClick={() => void loadRules(page - 1)}>上一页</button> <button className="secondary-button" type="button" disabled={page >= totalPages || loading} onClick={() => void loadRules(page + 1)}>下一页</button></div>
      </div>
    </section>
  );
}

function AuditView() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuditLogs(50)
      .then(setRecords)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <section className="panel"><p style={{ padding: 40, textAlign: "center" }}>加载中...</p></section>;
  }

  return (
    <section className="panel">
      <PanelHeader icon={History} title="审计日志" meta={`${records.length} 条记录 · data/logs/audit-*.jsonl`} />
      {records.length === 0 ? (
        <EmptyState icon={FileText} title="暂无审计记录" text="运行链路演示后，记录将显示在此处" />
      ) : (
        <AuditTable records={records} />
      )}
    </section>
  );
}

function FeedbackView() {
  const [type, setType] = useState("false_positive");
  const [sample, setSample] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!sample.trim()) return;
    setSubmitting(true);
    try {
      await submitFeedback({ type, sample, suggestion });
      setSubmitted(true);
      setSample("");
      setSuggestion("");
    } catch (err) {
      console.error(err);
    }
    setSubmitting(false);
  }

  return (
    <section className="view-stack">
      <section className="panel">
        <PanelHeader icon={ClipboardList} title="误判反馈" meta="POST /api/feedback" />
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12, maxWidth: 500 }}>
          <label>
            <strong>反馈类型</strong>
            <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: "100%", marginTop: 4, padding: "6px 10px" }}>
              <option value="false_positive">误判（正常被判为违规）</option>
              <option value="false_negative">漏判（违规被判为正常）</option>
              <option value="wrong_category">分类错误</option>
            </select>
          </label>
          <label>
            <strong>样本内容</strong>
            <textarea
              value={sample}
              onChange={(e) => setSample(e.target.value)}
              placeholder="输入被误判/漏判的文本"
              style={{ width: "100%", marginTop: 4, minHeight: 80 }}
            />
          </label>
          <label>
            <strong>建议</strong>
            <input
              value={suggestion}
              onChange={(e) => setSuggestion(e.target.value)}
              placeholder="你的修改建议（可选）"
              style={{ width: "100%", marginTop: 4, padding: "6px 10px" }}
            />
          </label>
          <button className="primary-button" onClick={handleSubmit} disabled={submitting || !sample.trim()} type="button">
            <Send size={18} />
            <span>{submitting ? "提交中..." : "提交反馈"}</span>
          </button>
          {submitted && <p style={{ color: "#16a34a" }}>反馈已提交，感谢！</p>}
        </div>
      </section>

      <section className="panel api-panel">
        <PanelHeader icon={Database} title="后端接口" meta="联调清单" />
        <div className="endpoint-list">
          <Endpoint method="POST" path="/api/pipeline/check" text="执行输入检测、脱敏、LLM 调用、输出复检" />
          <Endpoint method="GET" path="/api/stats/overview" text="获取请求量、拦截率、类型占比、趋势数据" />
          <Endpoint method="GET" path="/api/rules" text="读取规则词库、启停状态、规则来源" />
          <Endpoint method="GET" path="/api/audit" text="读取审计日志" />
          <Endpoint method="POST" path="/api/feedback" text="提交误判、漏判、分类错误反馈" />
        </div>
      </section>
    </section>
  );
}

function PanelHeader({ icon: Icon, title, meta }: { icon: typeof MessageSquareText; title: string; meta: string }) {
  return (
    <div className="panel-header">
      <div>
        <Icon size={19} />
        <h2>{title}</h2>
      </div>
      <span>{meta}</span>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  trend,
  danger,
  warning,
}: {
  icon: typeof MessageSquareText;
  label: string;
  value: string;
  trend: string;
  danger?: boolean;
  warning?: boolean;
}) {
  return (
    <article className={`metric-card ${danger ? "danger" : ""} ${warning ? "warning" : ""}`}>
      <Icon size={22} />
      <span>{label}</span>
      <strong>{value}</strong>
      {trend && <small>{trend}</small>}
    </article>
  );
}

function RiskBadge({ level, compact }: { level: RiskLevel; compact?: boolean }) {
  return <span className={`risk-badge ${level} ${compact ? "compact" : ""}`}>{riskLevelLabels[level]}</span>;
}

function PipelineStep({ label, active, done, warning }: { label: string; active: boolean; done: boolean; warning?: boolean }) {
  return (
    <div className={`pipeline-step ${active ? "active" : ""} ${warning ? "warning" : ""}`}>
      <span>{warning ? <AlertTriangle size={15} /> : done ? <CheckCircle2 size={15} /> : <Activity size={15} />}</span>
      <strong>{label}</strong>
    </div>
  );
}

function TextBlock({ title, text, emphasized }: { title: string; text: string; emphasized?: boolean }) {
  return (
    <article className={emphasized ? "text-block emphasized" : "text-block"}>
      <span>{title}</span>
      <p>{text}</p>
    </article>
  );
}

function EmptyState({ icon: Icon, title, text }: { icon: typeof CheckCircle2; title: string; text: string }) {
  return (
    <div className="empty-state">
      <Icon size={28} />
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function ChartLegend() {
  return (
    <div className="chart-legend">
      <span><i className="passed" />放行</span>
      <span><i className="desensitized" />脱敏</span>
      <span><i className="blocked" />拦截</span>
    </div>
  );
}

function AuditTable({ records }: { records: AuditRecord[] }) {
  return (
    <div className="data-table">
      <div className="table-head audit-head">
        <span>请求 ID</span>
        <span>时间</span>
        <span>动作</span>
        <span>风险</span>
        <span>LLM</span>
        <span>输出复检</span>
        <span>耗时</span>
      </div>
      {records.map((record) => (
        <div className="table-row audit-row" key={record.requestId}>
          <span className="mono">{record.requestId}</span>
          <span>{record.timestamp}</span>
          <ActionPill action={record.action} />
          <RiskBadge level={record.riskLevel} compact />
          <span>{record.llmCalled ? "已调用" : "未调用"}</span>
          <span>{record.outputBlocked ? "已拦截" : "通过"}</span>
          <strong>{record.durationMs} ms</strong>
        </div>
      ))}
    </div>
  );
}

function ActionPill({ action }: { action: RiskAction }) {
  return <span className={`action-pill ${action}`}>{actionLabels[action]}</span>;
}

function Endpoint({ method, path, text }: { method: string; path: string; text: string }) {
  return (
    <article className="endpoint-item">
      <span>{method}</span>
      <strong>{path}</strong>
      <p>{text}</p>
    </article>
  );
}

export default App;