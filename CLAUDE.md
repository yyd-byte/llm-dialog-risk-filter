# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

面向聊天/问答/客服场景的轻量级大模型内容风控系统，采用 **规则 + 语义双层过滤**，实现输入拦截、片段脱敏、输出复检、日志统计全闭环，支持风险分级与可解释审计。

- GitHub 仓库：`https://github.com/yyd-byte/llm-dialog-risk-filter`
- 队长：`yyd-byte`，协作者：`Grayy9` `MyDear7251`（当前用户：`Grayy9`）

## 技术栈

- 语言：Python 3.10+
- 配置：YAML
- 看板：Streamlit
- 语义模型：sentence-transformers / transformers
- LLM 调用：Ollama / OpenAI 兼容 API
- 平台：Windows 11，Git Bash shell

## 项目结构

```
├── config/
│   ├── default.yaml          # 全局配置（阈值、模型路径、LLM 参数等）
│   └── rules/                # 四类风险规则（YAML，可编辑可更新）
│       ├── sexual.yaml       # 色情低俗
│       ├── violent.yaml      # 暴力危险
│       ├── advertising.yaml  # 广告引流
│       └── sensitive.yaml    # 敏感话术
├── src/
│   ├── detection/            # 检测层：normalizer + rule_detector + semantic_detector
│   ├── rules/                # 规则管理：models + repository(YAML读写) + manager(CRUD)
│   ├── decision/             # 决策层：models(RiskLevel/RiskResult) + fusion(规则+语义融合)
│   ├── desensitization/      # 脱敏：片段级替换，保留语义
│   ├── output_check/         # 输出复检：LLM 回复二次校验+安全兜底
│   ├── audit/                # 审计：logger(JSONL) + statistics(聚合统计)
│   ├── llm/                  # LLM 客户端：Ollama / OpenAI 兼容
│   ├── dashboard/            # Streamlit 运营看板
│   └── utils/                # 自定义异常
├── demo/
│   ├── cli_demo.py           # 命令行演示入口（--interactive / --scenario N）
│   └── scenarios.py          # 预设演示场景
├── tests/                    # 单元测试 & 集成测试
├── scripts/
│   ├── download_model.py     # 下载语义模型
│   └── init_rules.py         # 初始化规则库
└── data/                     # 运行时数据（logs/、models/、feedback/）
```

## 核心数据流

```
用户输入 → TextNormalizer → RuleDetector + SemanticDetector
  → RiskFusion → RiskLevel(HIGH/MEDIUM/LOW)
  → HIGH: 直接拦截
  → MEDIUM: Desensitizer 脱敏 → LLM 调用 → OutputChecker
  → LOW: 直接 LLM 调用 → OutputChecker
  → AuditLogger 记录 → 返回结果
```

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 代码质量检查（提交前运行）
python -m pytest tests/ -v
ruff check src/ tests/ demo/ scripts/   # lint
ruff format --check src/ tests/ demo/ scripts/  # 格式检查

# 运行演示（所有预设场景）
python demo/cli_demo.py

# 交互模式
python demo/cli_demo.py --interactive

# 指定场景
python demo/cli_demo.py --scenario 0

# 不连接 LLM（模拟模式）
python demo/cli_demo.py --no-llm

# 运行测试
python -m pytest tests/ -v

# 启动 API 服务（后端）
python -m uvicorn src.api.server:app --reload --port 8000

# 启动看板
streamlit run src/dashboard/app.py

# 下载语义模型
python scripts/download_model.py

# 初始化规则库
python scripts/init_rules.py
```

## 编码规范

- **后端**：参见 `BACKEND_CONVENTIONS.md`，所有 Python 代码必须遵守
- **前端**：参见 `frontend/README.md`，TypeScript + React 约定

## 配置要点

- `config/default.yaml` 是全局配置文件
- 规则文件在 `config/rules/`，每个类别一个 YAML，支持 `keywords` 和 `regex` 两种模式
- 规则可动态启停，无需重启系统
- 语义模型默认使用 `shibing624/text2vec-base-chinese`，未加载时自动回退到纯规则模式
- 审计日志以 JSONL 格式写入 `data/logs/`，原始文本脱敏后存储

## 风险等级

| 等级 | 含义 | 处置 |
|------|------|------|
| HIGH | 明显违规 | 直接拦截，返回合规提示 |
| MEDIUM | 疑似违规 | 脱敏后继续处理 |
| LOW | 正常 | 直接放行 |