# llm-dialog-risk-filter
面向聊天/问答/客服场景的轻量级大模型内容风控系统，采用规则+语义双层过滤，实现输入拦截、片段脱敏、输出复检、日志统计全闭环，支持风险分级与可解释审计。

## 前端网页

本项目已新增独立网页前端，目录位于 `frontend/`，用于展示输入检测、风险分级、脱敏放行、输出复检、运营看板、规则管理、审计日志和误判反馈等模块。

```bash
cd frontend
pnpm install
pnpm dev
```

启动后访问：

```text
http://127.0.0.1:5173/
```

## 后端 API

```bash
python -m uvicorn src.api.server:app --reload --port 8000
```

API 文档：启动后访问 `http://127.0.0.1:8000/docs`

| 端点 | 说明 |
|------|------|
| `POST /api/pipeline/check` | 完整风控流水线 |
| `GET /api/stats/overview` | 运营统计 |
| `GET /api/rules` | 规则词库 |
| `GET /api/audit` | 审计日志 |
| `POST /api/feedback` | 误判反馈 |

## 模型

| 用途 | 模型 | 来源 |
|------|------|------|
| 语义检测 | BAAI/bge-small-zh-v1.5 | 本地（HuggingFace 镜像） |
| 对话生成 | deepseek-chat | DeepSeek API |

LLM 支持切换其他 OpenAI 兼容服务（通义千问、智谱、Ollama 等），修改 `config/default.yaml` 即可。
