# 贡献指南

感谢参与本项目。仓库由三人协作维护，请通过分支和 Pull Request 交付变更。

## 基本规则

1. 不直接向 `main` 推送。
2. 一项功能、规则导入或文档更新使用一个主题明确的分支：

   ```bash
   git checkout main
   git pull --ff-only
   git checkout -b feature/short-description
   ```

3. 不提交 `.env`、`.env.*`、API Key、`RULES_ADMIN_TOKEN`、模型文件、运行日志或反馈数据。
4. 前端统一使用 pnpm；不要提交 `frontend/package-lock.json`。
5. 小而聚焦的提交优于混合大量无关重构的提交。

## 提交前检查

```bash
python -m pytest tests/ -v
ruff check src/ tests/ demo/ scripts/
ruff format --check src/ tests/ demo/ scripts/
cd frontend && pnpm build
```

涉及规则、融合、规范化或词库时，还应运行：

```bash
python scripts/evaluate.py --no-semantic --output json
python scripts/benchmark_rule_detector.py --iterations 100
```

评估脚本在存在误判时退出码为 1；请在 PR 中说明指标、模式和已有基线，不要将其误报为脚本崩溃。

## 规则和配置变更

`config/rules/`、词库 mapping/manifest、风险阈值及脱敏策略属于高影响变更：

- 在 PR 中说明来源、许可证、预期风险等级、潜在误报影响与回滚方案。
- 第三方词库导入必须先 dry-run，再审查 diff，并提交 mapping、manifest、第三方声明的相关更新。
- 至少需要规则维护者和另一位成员审查。
- 运行中服务不会自动读取手动 YAML 改动；部署后由规则维护者执行授权 reload 或重启。

## Pull Request 内容

PR 描述至少包含：

- 变更目的和影响模块；
- 是否影响真实 LLM、语义模式、规则库或前端；
- 配置/迁移/reload 要求；
- 执行的测试、构建、评估和基准命令及结果；
- 安全或隐私影响；
- 回滚方式。

## 冲突与回滚

合并前同步 `main`、解决冲突并重新运行受影响检查。规则问题优先用 Git revert 恢复经审查版本，再由维护者 reload；不要从未知本地备份直接覆盖共享 YAML。

完整操作说明见 [使用手册](docs/USAGE_MANUAL.md)。
