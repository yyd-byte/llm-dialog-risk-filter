# 大模型内容风控系统前端

这是面向答辩和联调的网页前端，基于 Vite + React + TypeScript 实现。当前后端接口尚未完成，页面通过 `src/api.ts` 中的 mock adapter 模拟检测链路，字段命名尽量对齐现有 Python 后端的数据模型。

## 页面模块

- 链路演示：展示输入规范化、规则召回、语义判断、风险融合、输出复检和最终处置。
- 运营看板：展示请求趋势、明显违规拦截率、脱敏放行、输出复检拦截、风险类别占比。
- 规则中心：展示四类风险规则的分类、启停、等级、来源和更新时间。
- 审计日志：展示请求 ID、时间、动作、风险等级、是否调用 LLM、输出复检状态和耗时。
- 误判反馈：展示误拦截、漏拦截、分类错误的反馈闭环。

## 本地运行

```bash
cd frontend
pnpm install
pnpm dev
```

默认访问地址：

```text
http://127.0.0.1:5173/
```

生产构建：

```bash
pnpm build
```

构建产物会生成到 `frontend/dist/`，可以部署到 Nginx、静态资源服务器或后端框架的静态目录。

## 待后端接入接口

当前页面预留了以下接口语义：

```text
POST /api/pipeline/check
GET  /api/stats/overview
GET  /api/rules
POST /api/feedback
```

后端完成后，优先替换 `src/api.ts` 中的 `runPipeline` 方法，再逐步把 `src/data.ts` 中的 mock 数据替换为真实接口请求。
