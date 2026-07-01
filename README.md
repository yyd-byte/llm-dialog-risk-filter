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

当前后端接口未完成，前端通过 mock adapter 占位，后续联调时主要替换 `frontend/src/api.ts` 和 `frontend/src/data.ts`。
