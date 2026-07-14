# funNLP 数据库整合 — 绕过变体检测扩展设计

**日期**: 2026-07-14
**状态**: 已确认
**来源**: https://github.com/fighting41love/funNLP

---

## 概述

从 funNLP 仓库提取 4 个 NLP 数据集，扩展项目的中文文本绕过检测能力：
拆字检测、同义词扩充、缩写展开、繁简转换。

---

## 1. 拆字检测（最高优先级）

### 数据来源

`funNLP/data/拆字词库/chaizi-jt.txt` — 17,951 条，格式 `字 \t 拆解1 [\t 拆解2]`，7,567 条有 2+ 拆法。

### Path A：规则变体预计算（主路径）

**流程**：敏感词关键字 → 逐字查拆字表 → 笛卡尔积拼接 → 生成新规则。

```
"赌博" → "赌"=["贝者"]  "博"=["十甫寸"]
      → 生成: "贝者十甫寸", "贝者 十甫寸"
      → 注入 config/rules/*.yaml, source="decomposition"
```

**实现**：`scripts/generate_decomposition_rules.py`
- 读入 1166 条规则中的中文关键词
- 为含 2+ 汉字的词生成所有拆字变体
- 注入对应类别规则文件，标记 `source: "decomposition"`
- 同时生成空格分隔和无空格两种变体

### Path B：非词典词还原（辅助）

**流程**：滑动窗口检测连续单字 → 尝试逆向拆字还原 → 词典验证 → 只还原非真实词。

```
"玩贝者十甫寸" → "贝者十甫寸" 逆拆 → "赌博" → 查词典不在 → 还原 ✓
"女子学校"     → "女子" 逆拆 → "好"     → 查词典存在 → 保留 ✗
```

**实现**：`src/detection/normalizer.py` 新增 `_normalize_decomposition()` 步骤。
- 词典来源：jieba 分词词库或公开中文词表
- 新配置 `config/decomposition_map.yaml`：`贝者: 赌`（拆字→原字反向映射）

### 预期效果

- Path A：为 1166 条规则中的多字关键词自动生成 300-600 条拆字变体规则
- Path B：捕获未知拆字绕过，词典验证防止误伤

---

## 2. 同义词库扩充

### 数据来源

`funNLP/data/同义词库、反义词库、否定词库/同义词库.txt` — 17,817 组（哈工大同义词词林）。

### 处理策略

用现有敏感词做种子，反向匹配同义词组，过滤高频日常词后生成 bypass_variants。

```
种子 "毒品" → 匹配到 "毒品 毒物 毒剂 毒药 毒"
           → 新增: 毒物→毒品, 毒剂→毒品, 毒药→毒品
           → "毒" 单字 → 跳过
```

**防误伤规则**：
- 单字词跳过
- 不与已有 bypass_variants 条目冲突
- 标记 `source: "hit_cir"` 可独立启停

### 实现

`scripts/expand_bypass_from_synonyms.py`
- 读入 `config/bypass_variants.yaml` 和同义词库
- 用现有 bypass_variants 的 key（中文部分）做种子
- 在同义词林中查找同义词组，提取新变体
- 输出到 `config/bypass_variants.yaml`（追加，不覆盖）

### 预期效果

新增 200-400 条高质量同音/同义绕过变体。

---

## 3. 缩写展开

### 数据来源

`funNLP/data/中文缩写库/` — 10,786 条（train + dev + test），格式 `缩写: 完整词1/词性 完整词2/词性 ...`。

### 处理策略

缩写展开为 normalizer 预处理步骤，展开后自然被现有规则命中。

```
"参赌" → "参加赌博" → 后续命中 "赌博" 关键词
```

### 实现

- 新配置 `config/abbreviation_map.yaml`（key=缩写, value=完整形式，去词性标签）
- `src/detection/normalizer.py` 新增 `_normalize_abbreviations()` 步骤
- `scripts/convert_abbreviation_data.py`：从 funNLP 原始格式转为 YAML

**注意**：缩写匹配需使用最长匹配优先，防止 "禁毒办" 中的 "禁毒" 先被错误展开。

---

## 4. 繁简转换

### 数据来源

`funNLP/data/繁简体转换词库/fanjian_suoyin.txt` — 5,908 对有差异的繁简字（共 17,803 行，同字行不计）。

### 处理策略

在 normalizer 全角→半角步骤后，新增繁→简转换步骤。

```
"亂倫" → "乱伦" → 命中规则
"倉庫" → "仓库"
```

### 实现

- 新配置 `config/traditional_simplified.yaml`（仅保留 5,908 对有差异的映射）
- `src/detection/normalizer.py` 新增 `_normalize_traditional_chinese()` 步骤
- `scripts/convert_traditional_simplified.py`：提取差异映射

---

## 改动文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `config/decomposition_map.yaml` | 拆字→原字反向映射（~17K 条） |
| 新增 | `config/abbreviation_map.yaml` | 缩写→完整形式（~10K 条） |
| 新增 | `config/traditional_simplified.yaml` | 繁体→简体（~6K 对） |
| 新增 | `scripts/generate_decomposition_rules.py` | Path A：拆字变体规则生成 |
| 新增 | `scripts/expand_bypass_from_synonyms.py` | 同义词库扩充 bypass |
| 新增 | `scripts/convert_abbreviation_data.py` | 缩写数据格式转换 |
| 新增 | `scripts/convert_traditional_simplified.py` | 繁简数据格式转换 |
| 修改 | `src/detection/normalizer.py` | 新增 3 个 normalize 步骤 + 拆字还原 |
| 修改 | `config/default.yaml` | 新增配置开关 |
| 修改 | `config/bypass_variants.yaml` | 追加同义词变体 |
| 修改 | `config/rules/*.yaml` | 追加拆字变体规则 |

---

## Normalizer 步骤顺序（更新后）

```
1. _normalize_full_to_half       (全角→半角)
2. _normalize_traditional        (繁→简)          ← 新增
3. _normalize_confusable_chars   (混淆字还原)
4. _normalize_abbreviations      (缩写展开)        ← 新增
5. _normalize_decomposition      (拆字还原 Path B) ← 新增
6. _normalize_bypass_variants    (短语级绕过)
7. _normalize_pinyin_variants    (拼音绕过)
8. _normalize_case               (大小写)
9. _strip_evasion_separators     (去分隔符)
10. _normalize_whitespace         (空白规范化)
11. _reduce_repeats               (压缩重复)
12. _normalize_symbols            (符号标准化)
```

步骤 2-4 在混淆字还原之前执行，确保繁体/缩写/拆字先被标准化，再走后续检测。

---

## 测试计划

- `tests/test_normalizer.py`：新增拆字还原、缩写展开、繁简转换的单元测试
- `tests/test_decomposition.py`：新增拆字 Path A 规则生成的集成测试
- 验证指标：敏感词绕过样本的检出率提升，正常文本的误报率不变
