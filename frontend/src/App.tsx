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
import { useMemo, useState } from "react";
import { runPipeline } from "./api";
import {
  actionLabels,
  auditRecords,
  categoryLabels,
  categoryStats,
  dailyStats,
  defaultResult,
  feedbackItems,
  riskLevelLabels,
  rules,
} from "./data";
import type { AuditRecord, PipelineResult, RiskAction, RiskLevel } from "./types";

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
  "这个边界投诉场景是否需要转人工处理？",
  "包含联系方式的广告引流占位样本，请触发脱敏流程。",
  "高风险违规占位样本，用于演示输入侧直接拦截。",
  "正常输入，但请演示输出复检安全兜底。",
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
            <strong>后端占位模式</strong>
            <span>API adapter: mock</span>
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
        <button className="icon-button" title="刷新 mock 数据" type="button">
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
    const next = await runPipeline(input);
    setResult(next);
    setLoading(false);
  }

  return (
    <section className="view-stack">
      <div className="console-grid">
        <section className="panel input-panel">
          <PanelHeader icon={Send} title="输入检测台" meta="mock /api/pipeline/check" />
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
        <div className="evidence-list">
          {result.evidenceChain.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="暂无风险证据" text="本次输入按低风险链路放行，已生成审计记录占位。" />
          ) : (
            result.evidenceChain.map((item, index) => (
              <article className="evidence-item" key={`${item.source}-${index}`}>
                <div>
                  <span className="source-pill">{item.source === "rule" ? "规则层" : "语义层"}</span>
                  <strong>{categoryLabels[item.category]}</strong>
                </div>
                <p>{item.explanation}</p>
                <span className="muted">
                  {item.matchedPattern} · 置信度 {Math.round(item.confidence * 100)}%
                </span>
              </article>
            ))
          )}
        </div>
      </section>
    </section>
  );
}

function DashboardView() {
  const totals = useMemo(() => {
    const total = dailyStats.reduce((sum, item) => sum + item.blocked + item.desensitized + item.passed, 0);
    const blocked = dailyStats.reduce((sum, item) => sum + item.blocked, 0);
    const outputBlocked = dailyStats.reduce((sum, item) => sum + item.outputBlocked, 0);
    return { total, blocked, outputBlocked, blockRate: blocked / total };
  }, []);

  return (
    <section className="view-stack">
      <div className="metric-grid">
        <MetricCard icon={Gauge} label="总请求数" value={totals.total.toLocaleString()} trend="+12.4%" />
        <MetricCard icon={ShieldX} label="明显违规拦截率" value={`${(totals.blockRate * 100).toFixed(1)}%`} trend="-1.8%" danger />
        <MetricCard icon={Sparkles} label="脱敏放行" value="172" trend="+7.1%" />
        <MetricCard icon={AlertTriangle} label="输出复检拦截" value={totals.outputBlocked.toString()} trend="+3" warning />
      </div>

      <div className="dashboard-grid">
        <section className="panel trend-panel">
          <PanelHeader icon={BarChart3} title="每日请求趋势" meta="最近 7 天" />
          <div className="stacked-chart">
            {dailyStats.map((day) => {
              const total = day.blocked + day.desensitized + day.passed;
              return (
                <div className="chart-row" key={day.date}>
                  <span>{day.date}</span>
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
            {categoryStats.map((item) => (
              <div className="category-row" key={item.category}>
                <span className="category-swatch" style={{ backgroundColor: item.color }} />
                <span>{item.label}</span>
                <div className="mini-track">
                  <i style={{ width: `${item.count}%`, backgroundColor: item.color }} />
                </div>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function RulesView() {
  const [query, setQuery] = useState("");
  const filtered = rules.filter((rule) => {
    const haystack = `${rule.id}${rule.pattern}${rule.description}${categoryLabels[rule.category]}`;
    return haystack.toLowerCase().includes(query.toLowerCase());
  });

  return (
    <section className="panel">
      <PanelHeader icon={Database} title="规则词库管理" meta="CRUD endpoint placeholder" />
      <div className="table-toolbar">
        <label className="search-box">
          <Search size={17} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索规则、类别或说明" />
        </label>
        <button className="secondary-button" type="button">
          <Download size={17} />
          <span>导入导出</span>
        </button>
      </div>
      <div className="data-table">
        <div className="table-head rules-head">
          <span>状态</span>
          <span>规则</span>
          <span>类别</span>
          <span>等级</span>
          <span>来源</span>
          <span>更新</span>
        </div>
        {filtered.map((rule) => (
          <div className="table-row rules-row" key={rule.id}>
            <span className="toggle-state">{rule.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}</span>
            <div>
              <strong>{rule.id}</strong>
              <span>{rule.pattern}</span>
              <small>{rule.description}</small>
            </div>
            <span>{categoryLabels[rule.category]}</span>
            <RiskBadge level={rule.riskLevel} compact />
            <span className="mono">{rule.source}</span>
            <span>{rule.updatedAt}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function AuditView() {
  return (
    <section className="panel">
      <PanelHeader icon={History} title="审计日志" meta="data/logs/audit-*.jsonl" />
      <AuditTable records={auditRecords} />
    </section>
  );
}

function FeedbackView() {
  return (
    <section className="view-stack">
      <section className="panel">
        <PanelHeader icon={ClipboardList} title="误判反馈闭环" meta="待接入 data/feedback" />
        <div className="feedback-grid">
          {feedbackItems.map((item) => (
            <article className="feedback-item" key={item.id}>
              <div>
                <strong>{item.id}</strong>
                <span className={`status-chip ${item.status}`}>{feedbackStatus(item.status)}</span>
              </div>
              <p>{item.sample}</p>
              <span>{item.suggestion}</span>
              <small>{item.timestamp}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="panel api-panel">
        <PanelHeader icon={Database} title="后端接口占位" meta="联调清单" />
        <div className="endpoint-list">
          <Endpoint method="POST" path="/api/pipeline/check" text="执行输入检测、脱敏、LLM 调用、输出复检" />
          <Endpoint method="GET" path="/api/stats/overview" text="获取请求量、拦截率、类型占比、趋势数据" />
          <Endpoint method="GET" path="/api/rules" text="读取规则词库、启停状态、规则来源" />
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
      <small>{trend}</small>
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

function feedbackStatus(status: "pending" | "reviewed" | "resolved") {
  const map = {
    pending: "待处理",
    reviewed: "已复核",
    resolved: "已解决",
  };
  return map[status];
}

export default App;
