# 完整使用手册

本文面向项目成员、演示人员和规则维护者。所有命令默认从仓库根目录执行：

```text
llm-dialog-risk-filter/
```

> 标记说明：**[全员]** 表示任何成员可执行；**[维护者]** 表示仅持有本地 `RULES_ADMIN_TOKEN` 的规则维护者执行；**[会修改共享规则]** 表示必须在分支和 PR 中审查。

## 系统架构

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 1. 文本规范化 (TextNormalizer)                        │
│    全半角转换 → 繁简转换 → 缩写展开 → 拆字还原         │
│    → 谐音/形近字替换 → 拼音感知 → 分隔符剥离            │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ 2. 双层过滤                                           │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ 规则检测 (第一层)  │  │ 语义检测 (第二层)  │        │
│  │ AC自动机 + 正则   │  │ BGE Embedding    │        │
│  │ 快速拦截明显违规   │  │ 二次语义判断      │        │
│  └────────┬─────────┘  └────────┬─────────┘        │
│           └──────────┬──────────┘                   │
│                      ▼                              │
│  ┌──────────────────────────────────┐              │
│  │ 3. 风险融合 (RiskFusion)          │              │
│  │    规则+语义加权融合 → 风险等级    │              │
│  └──────────────┬───────────────────┘              │
└─────────────────┼──────────────────────────────────┘
                  ▼
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌──────┐   ┌──────────┐   ┌──────┐
│ HIGH │   │ MEDIUM   │   │ LOW  │
│ 拦截 │   │ 脱敏后    │   │ 放行 │
│      │   │ 继续处理  │   │      │
└──────┘   └────┬─────┘   └──┬───┘
                │             │
                ▼             │
         ┌──────────┐        │
         │4. 脱敏    │        │
         │ 片段替换  │        │
         └────┬─────┘        │
              │              │
              ▼              ▼
         ┌──────────────────────┐
         │ 5. LLM 调用           │
         │    DeepSeek / Ollama  │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ 6. 输出复检            │
         │    LLM 回复二次校验    │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ 7. 审计日志            │
         │    JSONL 全链路记录    │
         └──────────────────────┘
```

---

## 1. 系统与运行模式

### 1.1 风控链路

```text
用户输入
→ TextNormalizer
→ RuleDetector + SemanticDetector
→ RiskFusion
→ LOW: 放行 / MEDIUM: 脱敏 / HIGH: 拦截
→ LLM（可选）
→ OutputChecker 输出复检
→ 审计日志、统计、反馈
```

| 风险等级 | 默认动作 | 含义 |
|---|---|---|
| `low` | `pass` | 正常或单个弱信号，直接放行 |
| `medium` | `desensitize` | 可疑内容，局部替换后继续处理 |
| `high` | `block` | 明显违规，直接阻断 |

规则层已采用 Aho-Corasick 自动机批量匹配关键词，regex 继续使用预编译 Python `re`。

### 1.2 支持的模式

| 模式 | 配置/命令 | 适用情况 |
|---|---|---|
| 规则层演示 | `--no-llm` 或评估 `--no-semantic` | 无 API Key、答辩稳定演示 |
| 本地语义模型 | `semantic_detection.mode: local`，CLI 加 `--load-model` | 使用本地 BGE 模型补充隐晦表达检测 |
| 语义 API | `semantic_detection.mode: api` + `SILICONFLOW_API_KEY` | 不下载本地 embedding 模型 |
| 模拟 LLM | CLI `--no-llm` | 不请求外部对话模型 |
| 真实 LLM | `.env` 配置 `DEEPSEEK_API_KEY`，按 `config/default.yaml` 设置 provider | 真实输入-输出闭环 |
| 脱敏 mask | `desensitization.mode: mask` | 用 `*` 替换片段 |
| 脱敏 semantic | `desensitization.mode: semantic` | 用类别标签替换，默认推荐 |
| 脱敏 rewrite | `desensitization.mode: rewrite` | 通过 LLM 改写，需外部模型可用 |

配置文件改动需**重启后端/CLI**才会生效；规则 YAML 改动可由维护者执行受控 reload 生效。

---

## 2. 首次安装

### 2.1 前置条件

- Git
- Python 3.10+
- Node.js 18+
- pnpm（团队唯一前端包管理器）

### 2.2 后端安装 [全员]

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

如需本地语义模型，首次加载时会下载/读取 `BAAI/bge-small-zh-v1.5`。也可先执行：

```bash
python scripts/download_model.py
```

### 2.3 前端安装 [全员]

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

只使用 `pnpm`。不要生成或提交 `frontend/package-lock.json`。

---

## 3. 快速体验（5 分钟）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key（可选，不配置则使用模拟模式）

```bash
# 在项目根目录创建 .env 文件
echo "DEEPSEEK_API_KEY=your-key-here" > .env
```

### 3. 运行命令行演示

```bash
# 模拟模式（不需要 API Key）
python demo/cli_demo.py --no-llm

# 交互模式（输入文本实时检测）
python demo/cli_demo.py --interactive --no-llm
```

### 4. 启动 API + 前端（完整体验）

```bash
# 终端 1：启动后端
python -m uvicorn src.api.server:app --reload --port 8000

# 终端 2：启动前端
cd frontend && pnpm install && pnpm dev
```

浏览器打开 http://localhost:5173 即可使用完整界面。

---

## 4. 本地环境变量与安全

### 4.1 创建 `.env` [全员]

```bash
cp .env.example .env
```

`.env`、`.env.*` 均被 Git 忽略。每位成员自行维护本地文件。

| 变量 | 是否必需 | 用途 | 所有权 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 真实 LLM 时需要 | DeepSeek/OpenAI 兼容对话调用 | 每位成员自己的 Key |
| `SILICONFLOW_API_KEY` | 语义 API 模式时需要 | 云端 embedding 调用 | 每位成员自己的 Key |
| `RULES_ADMIN_TOKEN` | 规则写操作才需要 | 规则启停与热更新 | **仅规则维护者保管** |

安全要求：

- 不提交 `.env`、不把 Key/token 放在 `config/default.yaml`、前端代码、Issue、PR、截图或聊天记录中。
- 管理 token 不共享给其他成员；其他成员通过 Git PR 修改共享规则。
- Key/token 暴露后立即在服务商或维护者本地撤销并重新生成。
- `data/logs/`、`data/feedback/` 可能包含敏感运行数据，禁止提交。

### 4.2 管理令牌示例 [维护者]

在维护者本地 `.env` 中填写随机长字符串：

```env
RULES_ADMIN_TOKEN=replace-with-a-long-random-local-value
```

前端规则中心的令牌输入框只在当前页面内存中保存，刷新页面后需要重新输入。

---

## 5. 启动与停止

### 5.1 启动后端 [全员]

```bash
python -m uvicorn src.api.server:app --reload --port 8000
```

验证：

```bash
curl http://127.0.0.1:8000/api/health
```

- API 文档：<http://127.0.0.1:8000/docs>
- 后端地址：`http://127.0.0.1:8000`

### 5.2 启动前端 [全员]

另开一个终端：

```bash
cd frontend
pnpm dev
```

访问：<http://127.0.0.1:5173/>

前端 API 地址当前固定为 `http://localhost:8000`。开发时应保持后端运行在 8000 端口；后端 CORS 只允许 Vite 的本地 5173 地址。

### 5.3 启动 Streamlit 看板 [全员]

```bash
streamlit run src/dashboard/app.py
```

端口与标题可在 `config/default.yaml` 的 dashboard 配置中调整。

### 5.4 停止服务

在启动服务的终端按 `Ctrl+C`。不要通过删除 `data/` 目录来"停止"服务。

---

## 6. CLI 演示

| 目标 | 命令 |
|---|---|
| 全部预设场景 | `python demo/cli_demo.py --no-llm` |
| 指定场景（从 0 开始） | `python demo/cli_demo.py --scenario 0 --no-llm` |
| 交互模式 | `python demo/cli_demo.py --interactive --no-llm` |
| 使用真实 LLM | `python demo/cli_demo.py` |
| 加载本地语义模型 | `python demo/cli_demo.py --load-model` |

`--no-llm` 使用模拟回复，适合无 Key 的稳定演示。真实 LLM 失败时应检查 `.env`、provider/base URL 与网络，而不是把 Key 写进代码。

> `--scenario` 必须使用有效索引；请先按默认全场景运行确认可用编号。

---

## 7. 配置参考

主要配置位于 `config/default.yaml`。

### 7.1 规则检测

```yaml
rule_detection:
  enabled: true
  rules_dir: config/rules
```

运行时只读取 `config/rules/` 的四个活动文件；`config/rules.bak/` 是备份/参考，不会被检测器加载。

### 7.2 语义检测

```yaml
semantic_detection:
  mode: local  # local 或 api
```

- `local`：本地模型；适合离线或可下载模型场景。
- `api`：云端 embedding；需要 `SILICONFLOW_API_KEY`。
- 模型不可用时系统会回退到规则层；日志会说明回退原因。

### 7.3 风险融合

`risk_fusion` 控制 high/medium 阈值、规则/语义权重和规则等级强度：

```yaml
rule_confidence:
  low: 0.2
  medium: 0.58
  high: 1.0
```

同一类别多个低风险独立信号会累积；high 规则为直接高风险信号。修改后必须重启应用或重新运行 CLI/评估脚本。

### 7.4 脱敏与输出检查

- `mask`：字符掩码。
- `semantic`：替换为类别标签。
- `rewrite`：调用 LLM 重写，需要真实 LLM 可用。

输出检查会再次检测 LLM 输出：LOW 放行，MEDIUM 尝试脱敏，HIGH 使用统一安全提示阻断。

---

## 8. 前端与 API 操作

### 8.1 普通功能 [全员]

前端提供：

- 链路演示：输入检测、风险等级、脱敏、输出复检。
- 运营看板：请求统计和类别分布。
- 审计记录：从本地 JSONL 汇总。
- 误判反馈：提交到 `data/feedback/feedback.jsonl`。
- 规则中心：分页、类别、来源、启停状态筛选。

### 8.2 规则管理 [维护者]

规则中心中的启停和"重新加载规则"需要输入 `RULES_ADMIN_TOKEN`。

| API | 说明 |
|---|---|
| `GET /api/rules` | 分页查询，支持 `page`、`page_size`、`category`、`source`、`enabled` |
| `GET /api/rules/metadata` | 当前 version、类别数量、来源数量 |
| `PATCH /api/rules/{id}/enabled` | 启用/停用规则，需 `X-Admin-Token` |
| `POST /api/rules/reload` | 从 YAML 重载并重建索引，需 `X-Admin-Token` |

启停 API body：

```json
{
  "enabled": false,
  "expectedVersion": "当前 metadata 返回的 version"
}
```

常见返回：

- `401`：令牌缺失或错误。
- `409`：规则版本已被其他变更更新；刷新列表、检查差异后再操作。
- `503`：后端未配置 `RULES_ADMIN_TOKEN`。
- `500`：规则 YAML 无法安全加载；检查 YAML 后重试，运行中的旧规则 snapshot 会保留。

成功启停会原子写入 YAML、重建关键词自动机/regex 缓存，并向：

```text
data/logs/rule-management-YYYY-MM-DD.jsonl
```

追加管理审计事件。

### 8.3 手动编辑 YAML 后 reload [会修改共享规则]

1. 在 feature branch 修改活动类别 YAML。
2. 执行测试、评估并在 PR 中审查 diff。
3. 合并/部署后，维护者在规则中心点击"重新加载规则"，或调用受保护 reload API。
4. 对比 metadata version 与启用数量；检查管理审计日志。

不要直接在生产运行目录随意编辑 YAML；回滚应优先通过 Git revert/恢复经审查版本，再 reload。

---

## 9. 规则库与第三方词库导入

### 9.1 活动规则文件

```text
config/rules/sexual.yaml
config/rules/violent.yaml
config/rules/advertising.yaml
config/rules/sensitive.yaml
```

每条规则包括：

```yaml
id: stable-rule-id
pattern: keyword-or-regex
pattern_type: keyword  # 或 regex
risk_level: low        # low / medium / high
enabled: true
description: operator-facing-description
source: manual-or-provenance
created_at: ISO-8601
updated_at: ISO-8601
```

keyword 使用批量自动机匹配；regex 使用 Python `re`。新增 regex 应简短、可审查，避免灾难性回溯。

### 9.2 houbb 标签词库导入 [会修改共享规则]

相关文件：

```text
scripts/import_sensitive_words.py
config/rules/houbb_sensitive_word_mapping.yaml
config/rules/houbb_sensitive_word_manifest.yaml
THIRD_PARTY_NOTICES.md
```

只导入经过审核的标签映射；禁止把无标签 deny/stop-word 词表整体归类导入。

```bash
# 1. 只预览，不修改文件
python scripts/import_sensitive_words.py --input <reviewed-tags-file>

# 2. 通过审核后写入 YAML 和 manifest
python scripts/import_sensitive_words.py --input <reviewed-tags-file> --apply

# 3. 验证已提交结果可从固定输入和策略复现
python scripts/import_sensitive_words.py --input <reviewed-tags-file> --check
```

`--prune-owned` 只能与 `--apply` 一起使用，会删除该导入器自己生成的陈旧规则；不得用于清理手工规则。导入必须在 feature branch 上完成，并同时提交规则 YAML、mapping、manifest 和第三方声明的必要更新。

### 9.3 其他生成脚本 [会修改共享规则]

`python scripts/init_rules.py` 和 `python scripts/generate_decomposition_rules.py` 都会修改类别 YAML。运行前创建分支、检查 Git diff、运行测试与评估；它们不是普通用户命令。

---

## 10. 质量、评估与性能

### 10.1 必跑检查 [全员]

```bash
python -m pytest tests/ -v
ruff check src/ tests/ demo/ scripts/
ruff format --check src/ tests/ demo/ scripts/
cd frontend && pnpm build
```

### 10.2 评估

```bash
# 全流程评估
python scripts/evaluate.py

# 快速规则层评估
python scripts/evaluate.py --no-semantic

# JSON 报告
python scripts/evaluate.py --no-semantic --output json
```

可用参数：`--cases-dir`、`--config`、`--rules-dir`、`--detail`。

评估数据位于 `data/test_cases/`。脚本只要存在误判就返回 exit code `1`；这表示质量报告中存在不匹配，不一定是脚本崩溃。PR 中应记录使用的分支/commit、模式和关键指标。

### 10.3 关键词匹配基准

```bash
python scripts/benchmark_rule_detector.py --iterations 100
```

基准输出规则数量、自动机构建耗时、短/长正常文本的平均和 P95 检测延迟。比较结果时应注明硬件、Python 版本、ruleset version 和迭代次数。

---

## 11. 三人 GitHub 协作流程

### 11.1 分工建议

| 角色 | 责任 |
|---|---|
| 规则维护者 | 保管 `RULES_ADMIN_TOKEN`，审核规则来源/许可证，执行受控 reload |
| 后端/算法成员 | 检测、融合、审计、API、测试与评估 |
| 前端/演示成员 | 前端、看板、演示脚本、使用文档与联调 |

实际成员可交叉协作，但规则/配置导入至少需要两人审查。

### 11.2 分支与 PR

```bash
git checkout main
git pull --ff-only
git checkout -b feature/short-description
```

- 不直接向 `main` 推送。
- 一项功能/规则导入/文档改动使用一个主题明确的分支。
- PR 至少包含：影响范围、运行模式、配置/规则迁移、测试命令与结果、评估/基准结果、回滚/reload 说明。
- `config/rules/`、mapping、manifest、风险阈值变更需要规则维护者和至少一位其他成员审查。
- 合并前同步 main、解决冲突并重新运行检查。

### 11.3 发布与回滚

- 记录发布 commit/tag 与 ruleset version。
- 代码/配置回滚使用 Git revert 或恢复经审查 commit。
- 部署后由维护者 reload 规则或重启后端。
- 不以手动复制未知 YAML 文件代替版本控制回滚。

---

## 12. 常见问题 FAQ

### Q: 语义模型下载失败怎么办？

国内网络使用 HuggingFace 镜像。在环境变量中设置：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

或在代码中已自动设置。若仍失败，系统自动回退到纯规则模式。

### Q: 如何添加新的敏感词？

1. 编辑 `config/rules/<类别>.yaml`，按现有格式添加规则条目
2. 通过 API 触发重载：`POST /api/rules/reload`
3. 或通过前端"规则中心"→"重载规则"按钮操作

### Q: 如何切换 LLM 提供商？

编辑 `config/default.yaml` 的 `llm` 段：

```yaml
llm:
  provider: "openai"  # 或 "ollama"
  base_url: "https://api.deepseek.com"  # 替换为目标 API 地址
  model: "deepseek-chat"
```

### Q: 误拦截了正常内容怎么办？

1. 通过前端"反馈"页提交误判反馈
2. 在 `config/rules/` 中调整对应规则的 `risk_level` 或 `enabled` 状态
3. 调整 `config/default.yaml` 中 `risk_fusion` 的阈值

### Q: 审计日志存储在哪里？

`data/logs/audit-YYYY-MM-DD.jsonl`，按天滚动。
原始文本经过 SHA-256 哈希化处理，保护用户隐私。

### Q: 后端无法启动？

确认虚拟环境和依赖：

```bash
pip install -r requirements.txt
python -m uvicorn src.api.server:app --reload --port 8000
```

端口被占用时更换端口，同时注意前端 API 地址默认固定为 8000。

### Q: 前端无法连接后端 / CORS 错误？

确认后端在 8000、前端在 5173。当前开发 CORS 仅允许 `localhost:5173` 和 `127.0.0.1:5173`。不要为了排错将 CORS 改为 `*` 并提交。

### Q: 语义模型加载失败？

系统会回退到规则层。检查网络、模型缓存、磁盘空间和 `semantic_detection.mode`；演示时可使用 `--no-llm` 或规则-only 评估。

### Q: 没有真实 API Key？

使用 CLI `--no-llm` 模拟模式。不要把临时/他人的 Key 写入代码。

### Q: 规则管理返回 401 / 409 / 503？

- `401`：维护者检查本地 token 是否正确。
- `409`：刷新规则 metadata 后检查并重试。
- `503`：后端维护者尚未在本地 `.env` 配置 token。

### Q: 手动修改 YAML 后未生效？

运行中的服务保留旧 snapshot。由维护者执行"重新加载规则"或重启后端；若 reload 失败，先修复 YAML 并保持旧规则继续运行。

### Q: 审计/反馈页面为空？

先执行一次链路检测或提交反馈；运行数据写入 `data/logs/`、`data/feedback/`，这些目录默认不提交 Git。

---

## 13. 安全与隐私检查表

提交或发起 PR 前确认：

- [ ] 未提交 `.env`、API Key、管理 token、日志、反馈、模型文件。
- [ ] 未将 token 写入前端环境变量或文档示例。
- [ ] 规则 YAML 改动有来源、风险等级和审查说明。
- [ ] 第三方词库改动包含许可证/manifest 更新。
- [ ] 已运行后端测试、Ruff、前端 pnpm build；规则改动已运行评估。
- [ ] 生产部署不直接暴露开发 API；配置 TLS、反向代理和实际身份认证后再开放网络访问。
