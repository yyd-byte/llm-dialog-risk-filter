# Task 7 Report: Polish USAGE_MANUAL.md for Competition Submission

## What was done

Revised `docs/USAGE_MANUAL.md` (472 lines -> 607 lines) for competition submission readiness. Three major additions plus full section renumbering.

### Changes to `docs/USAGE_MANUAL.md`

1. **Added system architecture ASCII diagram** (new section, after intro)
   - Complete end-to-end pipeline diagram: TextNormalizer -> dual-layer filter (RuleDetector + SemanticDetector) -> RiskFusion -> three-way routing (HIGH/MEDIUM/LOW) -> Desensitizer -> LLM call -> OutputChecker -> AuditLogger
   - 55-line ASCII art using box-drawing characters, color-free for PDF printing

2. **Added "快速体验（5 分钟）" quick-start section** (new section 3)
   - 4 steps: install deps, configure API key (optional), run CLI demo, launch API + frontend
   - Users can go from zero to running in approximately 5 minutes

3. **Reformatted FAQ section** (section 12, was section 11)
   - Converted from freeform troubleshooting format to consistent Q: / A: style
   - Merged 5 items from the SDD task brief with 6 existing items from original section 11
   - Added code blocks for LLM config YAML, HuggingFace mirror, and pip commands

4. **Renumbered sections 3-12 to 4-13**
   - Insertion of new section 3 required shifting all subsequent sections
   - All subsection headings (e.g., `### 4.1` -> `### 5.1`) updated consistently
   - No content lost from original; all original sections preserved with updated numbering

### Document structure (sections)

| # | Title | Source |
|---|-------|--------|
| -- | 系统架构 (Architecture) | **New** |
| 1 | 系统与运行模式 | Original |
| 2 | 首次安装 | Original |
| 3 | 快速体验（5 分钟） | **New** |
| 4 | 本地环境变量与安全 | Renumbered (was 3) |
| 5 | 启动与停止 | Renumbered (was 4) |
| 6 | CLI 演示 | Renumbered (was 5) |
| 7 | 配置参考 | Renumbered (was 6) |
| 8 | 前端与 API 操作 | Renumbered (was 7) |
| 9 | 规则库与第三方词库导入 | Renumbered (was 8) |
| 10 | 质量、评估与性能 | Renumbered (was 9) |
| 11 | 三人 GitHub 协作流程 | Renumbered (was 10) |
| 12 | 常见问题 FAQ | Reformatted (was 11) |
| 13 | 安全与隐私检查表 | Renumbered (was 12) |

## Verification

- All 13 sections sequentially numbered (## 1. through ## 13.)
- All subsection headings (`### X.Y`) match their parent section
- Architecture diagram uses monospace-safe box drawing characters
- Code blocks use language tags (`bash`, `yaml`, `json`, `text`, `env`) for syntax highlighting
- Consistent `---` section separators for clean PDF page break behavior
- FAQ format is uniform (all 11 entries use `### Q: ...` pattern)

## Status

- [x] Step 1: Architecture ASCII diagram added (after intro)
- [x] Step 2: Quick-start section added (section 3)
- [x] Step 3: FAQ section reformatted with merged content (section 12)
- [x] Step 4: All sections verified sequential; PDF-friendly formatting
- [x] Committed

## Commit

```
commit d2b5f37
Author: Grayy9
Date:   Mon Jul 20 2026

    docs: polish USAGE_MANUAL.md — add architecture diagram, quick-start, FAQ

    Files changed:
      M docs/USAGE_MANUAL.md
      A .superpowers/sdd/task-7-report.md
```
