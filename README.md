# LLM Dialog Risk Filter

面向聊天、问答与客服场景的轻量级大模型内容风控系统。系统通过**文本规范化 + 规则检测 + 语义检测 + 风险融合**完成输入拦截、片段脱敏、LLM 输出复检、审计与运营统计。

- 风险等级：`LOW` 放行、`MEDIUM` 脱敏、`HIGH` 拦截
- 风险类别：色情低俗、暴力危险、广告引流、敏感话术
- 规则库：本地 YAML，支持来源追踪、版本校验、受控热更新
- 前端：React + Vite；后端：FastAPI；看板：Streamlit

> **安全提示**：不要提交 `.env`、API Key、`RULES_ADMIN_TOKEN`、运行日志、反馈记录或模型文件。完整的部署与协作说明见 [使用手册](docs/USAGE_MANUAL.md)。

## 快速开始

### 1. 安装依赖

```bash
# Python 3.10+
python -m venv .venv
# Windows Git Bash
source .venv/Scripts/activate
pip install -r requirements.txt

# Node.js + pnpm
cd frontend
pnpm install --frozen-lockfile
cd ..
```

### 2. 配置本地环境变量

复制模板为本地文件：

```bash
cp .env.example .env
```

`.env` 不会进入 Git。普通成员只需在需要真实服务时填写自己的 API Key；`RULES_ADMIN_TOKEN` 仅规则维护者保管，其他成员无需配置。

### 3. 启动后端

```bash
python -m uvicorn src.api.server:app --reload --port 8000
```

- 健康检查：<http://127.0.0.1:8000/api/health>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

### 4. 启动前端

另开一个终端：

```bash
cd frontend
pnpm dev
```

访问 <http://127.0.0.1:5173/>。

### 5. 无密钥演示

没有 API Key 也可运行 CLI 的模拟 LLM 流程：

```bash
python demo/cli_demo.py --scenario 0 --no-llm
```

## 常用命令

| 目的 | 命令 |
|---|---|
| 完整 CLI 场景演示 | `python demo/cli_demo.py --no-llm` |
| CLI 交互模式 | `python demo/cli_demo.py --interactive --no-llm` |
| 加载本地语义模型 | `python demo/cli_demo.py --load-model` |
| 启动 Streamlit 看板 | `streamlit run src/dashboard/app.py` |
| 规则层评估 | `python scripts/evaluate.py --no-semantic` |
| 规则匹配基准 | `python scripts/benchmark_rule_detector.py` |
| 全量后端测试 | `python -m pytest tests/ -v` |
| Python Lint/格式检查 | `ruff check src/ tests/ demo/ scripts/ && ruff format --check src/ tests/ demo/ scripts/` |
| 前端生产构建 | `cd frontend && pnpm build` |

## 规则管理

规则中心支持按类别、来源、启停状态分页筛选。规则启停与 YAML 热更新需要维护者在页面临时输入本地 `RULES_ADMIN_TOKEN`；令牌不会保存到浏览器或仓库。

- `GET /api/rules`：分页规则查询
- `GET /api/rules/metadata`：规则版本、来源与数量汇总
- `PATCH /api/rules/{rule_id}/enabled`：受保护的启停
- `POST /api/rules/reload`：受保护的 YAML 热更新

手动修改 `config/rules/*.yaml` 后，必须由维护者执行“重新加载规则”或重启后端，才能让运行中的检测器使用新规则。

## 文档与协作

- [完整使用手册](docs/USAGE_MANUAL.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)
- [第三方词库声明](THIRD_PARTY_NOTICES.md)
- [后端编码规范](BACKEND_CONVENTIONS.md)

三人协作请使用 feature branch + Pull Request；不要直接向 `main` 推送规则、配置或代码变更。
