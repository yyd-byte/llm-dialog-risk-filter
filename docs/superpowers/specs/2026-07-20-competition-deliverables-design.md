# 竞赛交付物完善 — 设计方案

**日期**: 2026-07-20
**关联**: 2026 全国人工智能竞赛 — 题目 1：面向对话场景的大模型输入/输出违规内容过滤系统

---

## 背景

项目代码已完成核心功能开发（规则+语义双层过滤、分级处置、输出复检、审计日志），
30 个 Python 源文件约 3,600 行，13 个测试文件 139 个用例。
按竞赛要求需完善：代码注释、使用文档、实训报告、测试用例与截图。

## 方案选择

三阶段分步推进（方案 C），每阶段有明确里程碑，对应竞赛评分维度。

---

## 阶段 1：代码注释中文化 + 模块拆分

### 1.1 注释中文化

对全部 30 个 Python 源文件执行中文化：

- **模块级 docstring**：英文 → 中文，9 个空 `__init__.py` 补全
- **类级 docstring**：英文 → 中文，补全 `RuleVersionConflictError`
- **方法级 docstring**：英文 → 中文，补全 6 个缺失（`_semantic_label`、`category_label`、`_current_log_file`、`_ollama_chat`、`_openai_chat`）
- **行内注释**：7 个不足的文件补充关键逻辑注释（`keyword_automaton.py`、`rule_detector.py`、`manager.py`、`statistics.py`、`client.py`、`embedding_client.py`、`dashboard/app.py`）

按目录分 4 批执行：decision/rules/utils → detection → desensitization/output_check/llm → api/audit/dashboard。

### 1.2 模块拆分（保证功能不变）

1. `src/api/server.py`（811 行）→ 拆分为：
   - `src/api/routes/pipeline.py` — `/api/pipeline/check`
   - `src/api/routes/stats.py` — `/api/stats/overview`
   - `src/api/routes/rules.py` — 规则 CRUD
   - `src/api/routes/feedback.py` — 反馈
   - `src/api/routes/health.py` — 健康检查
   - `src/api/bootstrap.py` — 启动初始化
   - `src/api/server.py` — 仅保留 app 创建 + 路由注册

2. `src/detection/normalizer.py`（519 行）→ 不做拆分，只补充行内注释。

风险控制：拆分后运行 `python -m pytest tests/ -v` 确保全部通过。

---

## 阶段 2：文档交付物

### 2.1 完善 `docs/USAGE_MANUAL.md`

现有 471 行，补充：系统架构图（ASCII）、快速体验章节（5 分钟上手）、
界面截图说明、FAQ 常见问题、格式统一可导出 PDF。

### 2.2 新建 `docs/项目实训报告.md`

四部分内容：

1. **功能设计** — 系统目标、双层过滤架构、四类风险定义、三级分级处理
2. **流程说明** — 7 步处理流程（规范化→规则→语义→融合→脱敏→LLM→输出复检），每步配 ASCII 流程图
3. **测试结果** — 95 条标注用例评估：准确率、拦截率、误判率、各类别 F1
4. **问题总结** — 谐音绕过、拆字绕过、拼音绕过、短词误报等问题的解决方案，后续改进方向

---

## 阶段 3：测试交付物

### 3.1 新建 `docs/测试用例清单.md`

整理 139 个测试方法，按模块分类列出（规范化 47、脱敏 19、融合 13、规则检测 12、
语义检测 12、输出复检 5、评估 13、集成 8、规则管理 5、词库导入 5）。

### 3.2 运行测试并截图

- `python -m pytest tests/ -v` 全量通过截图
- `python scripts/evaluate.py` 评估指标输出截图
- `python demo/cli_demo.py` 各风险等级处置效果截图

---

## 不做的范围

- 不新增功能特性（只完善现有代码的注释和文档）
- 不对 normalizer.py 做大规模重构（内部方法边界已清晰）
- 不修改规则 YAML 文件内容
- 不修改前端代码
- 不新增依赖

## 质量门槛

- 全部测试通过：`python -m pytest tests/ -v`
- Lint 通过：`ruff check src/ tests/`
- 格式通过：`ruff format --check src/ tests/`
- 评估指标达标：拦截率 ≥ 90%，误判率 ≤ 5%
