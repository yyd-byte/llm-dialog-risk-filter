# 前端开发说明

前端采用 React + TypeScript + Vite，位于 `frontend/`。它通过 `src/api.ts` 调用真实 FastAPI 后端，不使用 mock 数据。

## 团队统一工具

项目统一使用 **pnpm**：

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm build
pnpm preview
```

请不要使用 npm 生成或提交 `package-lock.json`。

## 本地开发

先在仓库根目录启动后端：

```bash
python -m uvicorn src.api.server:app --reload --port 8000
```

再启动前端：

```bash
cd frontend
pnpm dev
```

默认地址：

- 前端：`http://127.0.0.1:5173/`
- 后端：`http://127.0.0.1:8000/`
- API 文档：`http://127.0.0.1:8000/docs`

当前 API base 固定为 `http://localhost:8000`，见 `src/api.ts`。开发后端必须使用 8000 端口；后端只允许本地 Vite 5173 来源跨域访问。

## 前端功能

- 链路演示：输入检测、风险等级、脱敏、输出复检。
- 运营看板：请求统计与风险类别分布。
- 规则中心：按类别、来源、启停状态分页筛选规则。
- 审计与反馈：查看本地审计摘要、提交误判反馈。

规则中心的启停与 YAML reload 是维护者操作：维护者在页面临时输入本地 `RULES_ADMIN_TOKEN` 后才可执行。该 token 不应放进任何前端 `.env`、浏览器存储、源代码或截图中。

## 构建与发布前检查

```bash
pnpm build
```

该命令执行 TypeScript 构建和 Vite 生产构建。项目目前未配置独立前端测试框架；每次前端修改至少应运行 `pnpm build`，并与启动的后端完成一次实际联调。

完整操作流程、规则维护与团队协作规范见仓库根目录的 [使用手册](../docs/USAGE_MANUAL.md)。
