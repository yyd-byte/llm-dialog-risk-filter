# 竞赛交付物完善 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善代码注释（全中文化）、模块拆分、使用文档、实训报告、测试用例清单，满足 2026 全国人工智能竞赛题目 1 全部 5 项交付物要求。

**Architecture:** 三阶段推进 — 阶段 1 处理全部 30 个源文件的注释中文化 + server.py 拆分为 7 个路由模块；阶段 2 完善使用手册 + 新建实训报告；阶段 3 整理测试用例清单 + 运行截图。所有改动保证功能不变，测试全绿。

**Tech Stack:** Python 3.10+, FastAPI, YAML, pytest, ruff

## Global Constraints

- Python 3.10+ 语法（`str | None`，不用 `Optional[str]`）
- 行宽上限 100 字符
- 注释写中文，面向中文开发者
- 双引号用于面向用户的字符串，单引号用于内部标识符
- 所有公开函数必须有完整类型注解
- 不修改功能逻辑，不新增依赖
- 拆分后全部测试通过：`python -m pytest tests/ -v`
- Lint 通过：`ruff check src/ tests/`
- 格式通过：`ruff format --check src/ tests/`

---

### Task 1: 注释中文化第 1 批 — decision / rules / utils（7 文件）

**Files:**
- Modify: `src/decision/models.py`
- Modify: `src/decision/fusion.py`
- Modify: `src/rules/models.py`
- Modify: `src/rules/repository.py`
- Modify: `src/rules/manager.py`
- Modify: `src/utils/exceptions.py`
- Modify: `src/__init__.py`

**Interfaces:** 纯注释改动，不改变任何接口

- [ ] **Step 1: 中文化 `src/__init__.py`**

将第 3 行的英文模块 docstring：
```python
"""LLM Dialog Risk Filter — lightweight content safety for chat scenarios."""
```
改为：
```python
"""大模型对话内容风控系统 — 面向聊天/问答/客服场景的轻量级内容安全过滤。"""
```

- [ ] **Step 2: 中文化 `src/utils/exceptions.py`**

将每个异常类的英文 docstring 改为中文：
```python
"""风险过滤系统自定义异常。"""

class RiskFilterError(Exception):
    """所有风险过滤异常的基类。"""

class ConfigurationError(RiskFilterError):
    """配置无效或缺失时抛出。"""

class RuleLoadError(RiskFilterError):
    """规则文件加载或解析失败时抛出。"""

class DetectionError(RiskFilterError):
    """检测流水线遇到错误时抛出。"""

class ModelNotAvailableError(RiskFilterError):
    """语义模型未加载或不可用时抛出。"""

class LLMServiceError(RiskFilterError):
    """大模型服务调用失败时抛出。"""

class AuditLogError(RiskFilterError):
    """审计日志写入失败时抛出。"""
```

- [ ] **Step 3: 中文化 `src/decision/models.py`**

将模块 docstring 和所有类/enum docstring 改为中文：
```python
"""风险等级与决策相关数据模型。"""

class RiskLevel(str, Enum):
    """三级风险分类。

    HIGH:   高风险 — 直接拦截
    MEDIUM: 中风险 — 脱敏后放行
    LOW:    低风险/正常 — 直接放行
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class RiskCategory(str, Enum):
    """四类风险类别（按赛题规范定义）。

    SEXUAL:      色情低俗
    VIOLENT:     暴力危险
    ADVERTISING: 广告引流
    SENSITIVE:   敏感话术
    """
    SEXUAL = "sexual"
    VIOLENT = "violent"
    ADVERTISING = "advertising"
    SENSITIVE = "sensitive"

class DetectionSource(str, Enum):
    """检测结果来源。

    RULE:     规则引擎命中
    SEMANTIC: 语义模型判断
    """
    RULE = "rule"
    SEMANTIC = "semantic"

@dataclass
class Evidence:
    """单条风险证据。

    记录产生证据的流水线步骤、命中内容、置信度及可解释说明。
    """
    source: DetectionSource
    category: RiskCategory
    confidence: float  # 0.0 ~ 1.0
    matched_pattern: str = ""  # 命中的关键词/正则
    matched_text: str = ""     # 命中的原文片段
    explanation: str = ""      # 可解释的说明
    step: str = ""             # 产生证据的流水线步骤: "normalize" | "rule" | "semantic" | "fusion" | "desensitize"
    declared_risk_level: RiskLevel | None = None  # 规则配置声明的风险等级；语义证据保持为空
    metadata: dict = field(default_factory=dict)  # 附加结构化数据，用于前端可视化

@dataclass
class RiskResult:
    """单侧（输入或输出）的统一风险评估结果。"""
    risk_level: RiskLevel
    risk_category: RiskCategory | None = None
    confidence: float = 0.0  # 0.0 ~ 1.0
    evidence_chain: list[Evidence] = field(default_factory=list)
    is_safe: bool = True  # LOW 时为 True，否则为 False

    def __post_init__(self):
        self.is_safe = self.risk_level == RiskLevel.LOW

    @property
    def action(self) -> str:
        """根据风险等级返回对应的处置动作。"""
        actions = {
            RiskLevel.HIGH: "block",
            RiskLevel.MEDIUM: "desensitize",
            RiskLevel.LOW: "pass",
        }
        return actions[self.risk_level]
```

- [ ] **Step 4: 中文化 `src/decision/fusion.py`**

模块 docstring 和所有方法 docstring 改为中文：
```python
"""风险融合 — 将规则和语义检测结果合并为统一的风险决策。"""

@dataclass
class FusionConfig:
    """风险融合配置。

    用于控制融合策略的阈值、权重和规则层置信度映射。
    """
    high_threshold: float = 0.8
    medium_threshold: float = 0.4
    rule_weight: float = 0.5
    semantic_weight: float = 0.5
    rule_confidence: dict[RiskLevel, float] = field(
        default_factory=lambda: {
            RiskLevel.LOW: 0.2,
            RiskLevel.MEDIUM: 0.58,
            RiskLevel.HIGH: 1.0,
        }
    )

    def __post_init__(self) -> None:
        """校验阈值、权重和规则层置信度的合法性。

        Raises:
            ValueError: 当 rule_confidence 未覆盖所有风险等级、置信度不满足
                        0 <= low < medium < high <= 1、阈值不满足
                        0 <= medium < high <= 1、权重为负数、或两个权重同时为零时抛出。
        """
        ...

def fusion_config_from_dict(config: dict) -> FusionConfig:
    """从 YAML 字典构建已验证的融合配置。

    Args:
        config: YAML 中 risk_fusion 段的配置字典。

    Returns:
        校验通过的 FusionConfig 实例。
    """
    ...

class RiskFusion:
    """将规则和语义证据融合为可解释的风险决策。

    融合策略：
    1. 任一规则声明 HIGH → 直接定级 HIGH
    2. 同类别内，规则层 noisy-or 聚合 + 语义层取最大值，加权平均
    3. 跨类别取最高分，按阈值定级 HIGH/MEDIUM/LOW
    """

    def evaluate(
        self,
        rule_evidence: list[Evidence],
        semantic_evidence: list[Evidence] | None = None,
    ) -> RiskResult:
        """对规则和语义证据进行融合，输出统一的风险评估结果。

        Args:
            rule_evidence: 规则检测层产生的证据列表。
            semantic_evidence: 语义检测层产生的证据列表，可为 None。

        Returns:
            包含风险等级、类别、置信度和完整证据链的 RiskResult。
        """
        ...

    # 其余方法 docstring 同样翻译为中文（evaluate_input, evaluate_output,
    # _category_score, _deduplicate_rule_evidence, _noisy_or, _max_confidence,
    # _best_category, _risk_level_for, _first_category, evidence_summary）
```

- [ ] **Step 5: 中文化 `src/rules/models.py`**

```python
"""规则与规则类别数据模型。"""

@dataclass
class Rule:
    """单条检测规则（关键词或正则）。"""
    id: str                       # 规则唯一标识
    pattern: str                  # 关键词或正则表达式
    pattern_type: str = "keyword" # "keyword" | "regex"
    category: RiskCategory = RiskCategory.SENSITIVE
    risk_level: RiskLevel = RiskLevel.HIGH
    enabled: bool = True
    description: str = ""         # 规则检测目标说明
    source: str = ""              # 规则来源标识
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class RuleMatch:
    """单次规则匹配结果。"""
    rule: Rule
    matched_text: str             # 实际命中的文本片段
    position: tuple[int, int] = (0, 0)  # 在规范化文本中的 (start, end)

@dataclass
class RuleCategoryMeta:
    """规则类别元数据。"""
    category: RiskCategory
    label: str             # 中文标签
    description: str       # 类别说明
    rule_count: int = 0
    enabled_count: int = 0
```

- [ ] **Step 6: 中文化 `src/rules/repository.py`**

模块和所有方法 docstring 改为中文：
```python
"""规则文件加载与原子化保存（YAML 后端）。"""

class RuleRepository:
    """从 YAML 文件加载并按原子方式保存规则。

    每个风险类别对应一个 YAML 文件，写入时先写临时文件再原子替换，
    防止并发读取到不完整数据。
    """

    def load_category(self, category: RiskCategory) -> list[Rule]:
        """加载单个类别的全部规则。

        Args:
            category: 风险类别枚举值。

        Returns:
            解析后的规则列表；文件不存在时返回空列表。
        """
        ...

    def load_all(self) -> dict[RiskCategory, list[Rule]]:
        """加载全部四类规则，返回类别到规则列表的映射。"""
        ...

    def save_category(self, category: RiskCategory, rules: list[Rule]) -> None:
        """原子化保存单个类别的规则，同时保留文件元数据。

        写入流程：创建临时文件 → 写入内容 → fsync → 原子 rename。
        """
        ...

    # 其余方法同样翻译（version, _parse_rule_file, _load_raw, _atomic_write,
    # _rule_to_dict, _category_label, _category_description）
```

- [ ] **Step 7: 中文化 `src/rules/manager.py`**

模块 docstring + 补全 RuleVersionConflictError docstring + 所有方法改为中文 +
补充 `set_rule_enabled` 方法行内注释：
```python
"""规则管理 — 查询、持久化及启用状态操作。

采用乐观锁版本控制，确保并发规则变更的安全性。
"""

class RuleVersionConflictError(Exception):
    """规则变更操作的目标版本与当前版本不一致时抛出。

    调用方应获取最新版本后重试。
    """

class RuleManager:
    """管理一份以 YAML 文件为后端的规则内存快照。

    提供规则的增删查改、启用/禁用、分页过滤及批量导入导出功能。
    所有写操作通过乐观锁（expected_version）防止并发冲突。
    """

    def set_rule_enabled(
        self,
        rule_id: str,
        enabled: bool,
        expected_version: str,
    ) -> tuple[Rule, str, bool]:
        """持久化规则的启用状态并返回更新后的规则、新版本和旧状态。

        使用乐观锁：expected_version 必须与当前版本一致，否则拒绝操作。
        同一规则重复设置为相同状态时直接返回（幂等）。
        """
        with self._lock:
            # 1. 版本检查 — 不匹配则拒绝
            current_version = self._repo.version()
            if expected_version != current_version:
                raise RuleVersionConflictError(current_version)
            # 2. 查找规则
            rule = self.get_rule_by_id(rule_id)
            if rule is None:
                raise KeyError(rule_id)
            # 3. 幂等检查 — 状态未变化则直接返回
            previous_enabled = rule.enabled
            if previous_enabled == enabled:
                return rule, current_version, previous_enabled
            # 4. 持久化整个类别的规则快照
            ...
```

- [ ] **Step 8: 验证第 1 批通过测试**

```bash
python -m pytest tests/test_fusion.py tests/test_rule_manager.py tests/test_rule_repository.py -v
```
预期：全部 PASS。

---

### Task 2: 注释中文化第 2 批 — detection（5 文件）

**Files:**
- Modify: `src/detection/__init__.py`
- Modify: `src/detection/keyword_automaton.py`
- Modify: `src/detection/normalizer.py`
- Modify: `src/detection/rule_detector.py`
- Modify: `src/detection/semantic_detector.py`

**Interfaces:** 纯注释改动

- [ ] **Step 1: 中文化 `src/detection/__init__.py`**

添加模块 docstring，保留原有 re-export 逻辑：
```python
"""检测层 — 文本规范化、关键词匹配、规则检测、语义检测。

对外暴露 TextNormalizer、RuleDetector、SemanticDetector 三个核心类。
"""

from src.detection.normalizer import TextNormalizer
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector

__all__ = ["TextNormalizer", "RuleDetector", "SemanticDetector"]
```

- [ ] **Step 2: 中文化 `src/detection/keyword_automaton.py`**

模块 docstring + 类/方法 docstring 改为中文 + 补充 BFS 构建失败链接的行内注释：
```python
"""无外部依赖的 Aho-Corasick 自动机，用于关键词字面量规则匹配。

支持在单次文本扫描中同时匹配大量关键词，时间复杂度 O(n+m)，
其中 n 为文本长度，m 为匹配到的模式总数。
"""

class KeywordAutomaton:
    """在单次文本扫描中匹配大量小写 Unicode 关键词模式。

    基于经典的 Aho-Corasick 算法实现，包含 trie 构建和失败链接 BFS。
    """

    def search(self, text: str) -> set[int]:
        """在文本中搜索，返回至少命中一次的所有规则序号。

        Args:
            text: 待搜索的小写文本。

        Returns:
            命中规则的序号集合（每个规则最多出现一次）。
        """
        ...

    def _build_failure_links(self) -> None:
        """所有模式插入完成后，通过 BFS 构建失败链接。

        失败链接的作用：当当前状态无法匹配下一字符时，跳转到
        trie 中最长后缀对应的状态，避免回溯文本指针。
        同时将失败目标状态的输出合并到当前状态（输出合并），
        确保不遗漏较短模式的匹配。
        """
        queue: deque[int] = deque()
        # 第一层（深度 1）的失败链接全部指向根节点 0
        for child in self._nodes[0].children.values():
            queue.append(child)

        while queue:
            state = queue.popleft()
            for character, child in self._nodes[state].children.items():
                queue.append(child)
                # 从父节点的失败链接开始，沿失败链向上查找
                # 直到找到包含相同字符的子节点或回到根节点
                failure = self._nodes[state].failure
                while failure and character not in self._nodes[failure].children:
                    failure = self._nodes[failure].failure
                # 设置子节点的失败链接
                self._nodes[child].failure = (
                    self._nodes[failure].children.get(character, 0)
                )
                # 输出合并：子节点继承失败链接目标的输出
                self._nodes[child].outputs.extend(
                    self._nodes[self._nodes[child].failure].outputs
                )
```

- [ ] **Step 3: 中文化 `src/detection/normalizer.py`**

这是最大的文件（519 行），已有较好的英文 docstring。将所有 docstring 翻译为中文，
重点补充以下复杂方法的中文行内注释：
- `_normalize_bypass_variants` — 解释 CJK/ASCII 分支匹配策略
- `_normalize_pinyin_variants` / `_pinyin_cjk_replace` — 解释滑动窗口拼音匹配
- `_normalize_abbreviations` — 解释两阶段占位符替换
- `_normalize_decomposition` — 解释词典验证步骤
- `_strip_evasion_separators` — 解释隔离检测算法

模块 docstring 示例：
```python
"""文本规范化 — 在检测前对输入文本进行预处理，消除各种绕过手段。

规范化步骤（按顺序执行）：
1. 全角 → 半角转换
2. 繁 → 简转换
3. 缩写展开
4. 拆字还原
5. 绕过变体替换（谐音/形近/拼音）
6. 混淆字标准化
7. 拼音变体感知
8. 大小写归一化
9. 绕过分隔符剥离
10. 空白字符合并
11. 重复字符压缩
12. 符号标准化
"""
```

- [ ] **Step 4: 中文化 `src/detection/rule_detector.py`**

模块和类/方法 docstring 改为中文，补充检测流程行内注释：
```python
"""基于规则的检测引擎 — 关键词和正则匹配。"""

class RuleDetector:
    """快速规则检测，同时支持关键词（AC 自动机）和正则表达式。

    检测流程：
    1. AC 自动机扫描全部关键词（单次遍历，O(n)）
    2. 逐条正则编译匹配
    3. 按声明顺序收集证据，每条规则最多产生一条证据

    线程安全：通过 RLock 保护缓存替换操作。
    """

    def detect(self, text: str) -> list[Evidence]:
        """对规范化文本执行规则检测。

        按规则声明顺序返回 Evidence 列表，每条命中规则对应一条证据。
        同一规则在文本中多次出现只记录一次。

        Args:
            text: 规范化后的输入文本。

        Returns:
            命中规则的 Evidence 列表；无命中时返回空列表。
        """
        text_lower = text.lower()
        regex_matches: dict[int, str] = {}

        # 获取线程安全的缓存快照
        with self._lock:
            ...

        # 第一步：AC 自动机扫描全部关键词（一次遍历）
        matched_ordinals = keyword_automaton.search(text_lower)
        # 第二步：逐条正则匹配
        for ordinal, compiled in compiled_regex.items():
            ...
        # 第三步：按声明顺序收集证据
        ...
```

- [ ] **Step 5: 中文化 `src/detection/semantic_detector.py`**

已有详细英文 docstring，全部翻译为中文。重点保留 BGE_QUERY_PREFIX 的注释说明。

- [ ] **Step 6: 验证第 2 批通过测试**

```bash
python -m pytest tests/test_normalizer.py tests/test_rule_detector.py tests/test_semantic_detector.py -v
```
预期：全部 PASS。

---

### Task 3: 注释中文化第 3 批 — desensitization / output_check / llm（5 文件）

**Files:**
- Modify: `src/desensitization/desensitizer.py`
- Modify: `src/output_check/checker.py`
- Modify: `src/llm/client.py`
- Modify: `src/llm/embedding_client.py`
- Modify: `src/detection/__init__.py`（已在 Task 2 完成）

**Interfaces:** 纯注释改动 + 补全缺失的方法 docstring

- [ ] **Step 1: 中文化 `src/desensitization/desensitizer.py` + 补全缺失 docstring**

模块 docstring + 类 docstring 翻译，补充 `_semantic_label` 和 `category_label` 的 docstring：
```python
"""片段级脱敏 — 替换敏感片段，保留句子结构和语义，避免整句删除。

支持三种脱敏模式：
- "mask":     用 *** 替换（保留首尾字符）
- "semantic": 用类别标签替换，如微信号 → [联系方式]，保留语义意图供 LLM 理解
- "rewrite":  语义标签替换 + LLM 自然化重写，将标签化的文本改写为自然安全的中文表达
              无 LLM 时自动回退到 semantic 模式。
"""

class Desensitizer:
    """替换敏感片段，保留句子结构。

    三种工作模式：
    mask     — *** 替换（旧版兼容）
    semantic — 类别标签替换：微信号 → [联系方式]
    rewrite  — 标签 + LLM 自然化：[联系方式] → 私下联系

    rewrite 模式下通过 llm_call 参数传入 LLM 调用函数，无 LLM 时自动回退。
    """

    def _semantic_label(self, evidence: Evidence | None) -> str:
        """根据证据的风险类别返回对应的语义替换标签。

        Args:
            evidence: 命中的证据对象。

        Returns:
            类别对应的语义标签字符串，如 [联系方式]、[不雅用语] 等。
        """
        ...

    def category_label(self, category: RiskCategory) -> str:
        """获取风险类别的可读中文标签。

        Args:
            category: 风险类别枚举值。

        Returns:
            对应的中文标签，如"色情低俗内容"。
        """
        ...
```

- [ ] **Step 2: 中文化 `src/output_check/checker.py`**

模块和类 docstring 翻译为中文，保留风险等级处置逻辑的清晰注释：
```python
"""输出复检 — 对 LLM 生成的回复进行二次内容安全校验。"""

class OutputChecker:
    """对 LLM 输出进行二次安全校验，作为整个过滤链路的"安全网"。

    即使输入侧通过了检测，模型仍可能生成违规内容。
    本模块在输出返回用户之前再次扫描，按风险等级分三级处置：

    - HIGH:   完全拦截，返回合规提示话术
    - MEDIUM: 片段脱敏后放行
    - LOW:    直接放行

    依赖规则检测器 + 语义检测器 + 风险融合 +（可选）脱敏器。
    """
    ...
```

- [ ] **Step 3: 中文化 `src/llm/client.py` + 补全私有方法 docstring**

翻译已有 docstring + 补充 `_ollama_chat` 和 `_openai_chat` 的 docstring：
```python
"""大模型客户端 — 统一的对话补全接口，支持 Ollama 和 OpenAI 兼容 API。"""

class LLMClient:
    """统一的大模型对话客户端。

    支持两种后端：
    - ollama: 本地 Ollama 服务
    - openai: 任意 OpenAI 兼容 API（DeepSeek / 通义千问 / 智谱等）
    """

    def _ollama_chat(self, prompt: str) -> LLMResponse:
        """通过 Ollama 本地 API 发送对话请求。

        Args:
            prompt: 用户输入的提示文本。

        Returns:
            包含生成文本或错误信息的 LLMResponse。
        """
        ...

    def _openai_chat(self, prompt: str) -> LLMResponse:
        """通过 OpenAI 兼容 API（DeepSeek 等）发送对话请求。

        使用 httpx 发送 POST 请求，自动处理超时和错误响应。

        Args:
            prompt: 用户输入的提示文本。

        Returns:
            包含生成文本或错误信息的 LLMResponse。
        """
        ...
```

- [ ] **Step 4: 中文化 `src/llm/embedding_client.py`**

翻译已有英文 docstring：
```python
"""云端 Embedding API 客户端 — 将文本转换为向量表示。

支持 OpenAI 兼容的 Embedding API（如 SiliconFlow），
用于语义检测层的文本向量化和相似度计算。
"""
```

- [ ] **Step 5: 验证第 3 批通过测试**

```bash
python -m pytest tests/test_desensitizer.py tests/test_output_check.py -v
```
预期：全部 PASS。

---

### Task 4: 注释中文化第 4 批 — api / audit / dashboard（8 文件）

**Files:**
- Modify: `src/api/__init__.py`
- Modify: `src/api/models.py`
- Modify: `src/api/server.py`（拆分前先注释中文化）
- Modify: `src/audit/logger.py`
- Modify: `src/audit/statistics.py`
- Modify: `src/audit/rule_management.py`
- Modify: `src/dashboard/app.py`
- Modify: 所有空 `__init__.py`（补模块 docstring）

**Interfaces:** 纯注释改动

- [ ] **Step 1: 补充所有空 `__init__.py` 的模块 docstring**

```python
# src/utils/__init__.py
"""工具模块 — 自定义异常类。"""

# src/rules/__init__.py
"""规则管理模块 — 规则数据模型、YAML 文件读写、内存管理器。"""

# src/decision/__init__.py
"""决策模块 — 风险数据模型与规则/语义融合算法。"""

# src/desensitization/__init__.py
"""脱敏模块 — 片段级敏感词替换，支持 mask/semantic/rewrite 三种模式。"""

# src/output_check/__init__.py
"""输出复检模块 — LLM 回复二次安全校验。"""

# src/audit/__init__.py
"""审计模块 — JSONL 日志记录、规则变更审计、统计聚合。"""

# src/llm/__init__.py
"""大模型客户端模块 — 对话补全与 Embedding API 封装。"""

# src/dashboard/__init__.py
"""运营看板模块 — Streamlit 数据可视化。"""
```

- [ ] **Step 2: 中文化 `src/api/__init__.py`**

添加模块 docstring：
```python
"""API 服务模块 — FastAPI RESTful 接口。

提供流水线检测、统计查询、规则管理、反馈提交和审计日志等端点。
通过延迟导入避免循环依赖。
"""
```

- [ ] **Step 3: 中文化 `src/api/models.py`**

Pydantic 模型的 docstring 翻译为中文，保留字段类型注解：
```python
"""API 请求/响应数据模型（Pydantic）。

所有模型与前端 frontend/src/types.ts 中的类型定义保持同步。
"""
```

每个 Pydantic 模型的 docstring 翻译，例如：
```python
class PipelineResult(BaseModel):
    """流水线检测的响应结果。

    包含从输入规范化到最终输出的全链路信息。
    """
```

- [ ] **Step 4: 中文化 `src/api/server.py`**

翻译所有注释和 docstring。重点：
- `startup()` 函数各组件初始化步骤的注释
- `pipeline_check()` 7 步流水线的步骤注释
- 每个路由的 docstring

- [ ] **Step 5: 中文化 `src/audit/logger.py` + 补全 `_current_log_file` docstring**

```python
"""审计日志 — 以结构化 JSONL 格式记录每次请求的处理全链路。"""

class AuditLogger:
    """将结构化审计记录写入 JSONL 日志文件。

    特性：
    - 按天滚动的日志文件（audit-YYYY-MM-DD.jsonl）
    - 超大小自动轮转
    - 原始文本哈希化存储以保护隐私
    """

    def _current_log_file(self) -> Path:
        """获取当前日期的活动日志文件路径。

        Returns:
            形如 data/logs/audit-2026-07-20.jsonl 的 Path 对象。
        """
        ...
```

- [ ] **Step 6: 中文化 `src/audit/statistics.py` + 补充行内注释**

翻译 dataclass 和方法的 docstring，补充 `_process_log_file` 中聚合逻辑的行内注释。

- [ ] **Step 7: 中文化 `src/audit/rule_management.py`**

补充模块 docstring、类 docstring、方法 docstring：
```python
"""规则管理审计 — 记录规则启用/禁用和重载操作的审计轨迹。

写入独立的 JSONL 日志文件，用于追溯规则变更历史。
"""

class RuleManagementAuditLogger:
    """记录规则管理操作的审计日志。

    记录两类事件：
    - 规则启用状态变更（谁在何时启用了/禁用了哪条规则）
    - 规则重载操作（重载前后的版本号和规则数量）
    """
    ...
```

- [ ] **Step 8: 中文化 `src/dashboard/app.py` + 补充行内注释**

```python
"""Streamlit 运营看板 — 内容风控数据可视化。

展示请求量趋势、风险等级分布、类别占比、规则命中统计等。
"""

def main():
    """看板主入口。

    布局：
    1. 侧边栏 — 日期范围选择、刷新按钮
    2. 指标卡片行 — 总请求数、拦截率、误判率、LLM 调用量
    3. 图表区 — 日请求趋势图、风险类别饼图
    4. 详情表 — 最近违规记录列表
    """
    ...
```

- [ ] **Step 9: 验证第 4 批**

```bash
ruff check src/api/ src/audit/ src/dashboard/
```
预期：无 lint 错误。

---

### Task 5: 拆分 `src/api/server.py`（811 行 → 7 个文件）

**Files:**
- Create: `src/api/routes/__init__.py`
- Create: `src/api/routes/pipeline.py`
- Create: `src/api/routes/stats.py`
- Create: `src/api/routes/rules.py`
- Create: `src/api/routes/feedback.py`
- Create: `src/api/routes/health.py`
- Create: `src/api/bootstrap.py`
- Modify: `src/api/server.py`（缩减为 app 创建 + 路由注册）

**Interfaces:**
- Consumes: 现有 `server.py` 中的全部组件和路由逻辑
- Produces: 拆分后的路由模块，对外接口不变（URL 路径、响应格式完全一致）

- [ ] **Step 1: 创建 `src/api/routes/__init__.py`**

```python
"""API 路由模块 — 按功能拆分为独立的子路由文件。"""
```

- [ ] **Step 2: 创建 `src/api/bootstrap.py`**

将 startup 初始化逻辑（约 170 行）迁移为独立函数：

```python
"""API 服务启动初始化 — 创建并配置全部组件。

将各组件的构造逻辑集中于此，供 server.py 在 startup 事件中调用。
"""

from pathlib import Path
from typing import Optional

import yaml

from src.api.models import ...
from src.audit.logger import AuditLogger
from src.audit.rule_management import RuleManagementAuditLogger
from src.audit.statistics import StatisticsEngine
from src.decision.fusion import RiskFusion, fusion_config_from_dict
from src.desensitization.desensitizer import Desensitizer, DesensitizeConfig
from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.llm.client import LLMClient, LLMConfig
from src.output_check.checker import OutputChecker
from src.rules.manager import RuleManager
from src.rules.repository import RuleRepository


def load_config(project_root: Path) -> dict:
    """加载并注入环境变量后的全局配置。

    按优先级: .env 文件 > 系统环境变量 > default.yaml。
    """
    ...


def create_normalizer(project_root: Path) -> TextNormalizer:
    """创建文本规范化器，加载全部变体映射配置。"""
    ...


def create_rule_engine(project_root: Path, config: dict) -> tuple[RuleManager, RuleDetector]:
    """创建规则管理器和规则检测器。"""
    ...


def create_semantic_detector(config: dict) -> SemanticDetector:
    """创建语义检测器（本地模型或云端 API）。"""
    ...


def create_llm_client(config: dict) -> LLMClient | None:
    """创建 LLM 客户端，失败时返回 None（模拟模式）。"""
    ...


def create_audit_components(project_root: Path, config: dict) -> tuple[AuditLogger, RuleManagementAuditLogger, StatisticsEngine]:
    """创建审计日志、规则管理审计、统计引擎。"""
    ...


class AppComponents:
    """API 服务所需的全部组件容器。

    在 startup 事件中创建并注入到各路由模块。
    """
    normalizer: TextNormalizer
    rule_detector: RuleDetector
    rule_manager: RuleManager
    semantic_detector: SemanticDetector
    fusion: RiskFusion
    desensitizer: Desensitizer
    output_checker: OutputChecker
    audit_logger: AuditLogger
    rule_management_audit: RuleManagementAuditLogger
    stats_engine: StatisticsEngine
    llm_client: LLMClient | None
    config: dict
    rules_admin_token: str
    feedback_store: list[dict]
```

（`create_*` 函数的具体实现直接从 `server.py` 的 `startup()` 函数迁移）

- [ ] **Step 3: 创建 `src/api/routes/health.py`**

```python
"""健康检查端点。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health():
    """返回服务健康状态。

    Returns:
        包含服务状态、已加载规则数和模型可用性的字典。
    """
    from src.api.bootstrap import AppComponents
    components = AppComponents.get()
    return {
        "status": "ok",
        "rulesLoaded": sum(1 for _ in components.rule_manager.get_enabled_rules()),
        "semanticAvailable": (
            components.semantic_detector.is_available
            if components.semantic_detector
            else False
        ),
        "llmAvailable": components.llm_client is not None,
    }
```

- [ ] **Step 4: 创建 `src/api/routes/pipeline.py`**

将 `POST /api/pipeline/check` 的完整逻辑（约 185 行）迁移到此文件，
函数签名和使用 `AppComponents` 获取组件：

```python
"""流水线检测端点 — 内容风控的核心 API。"""

import time
import uuid

from fastapi import APIRouter

from src.api.bootstrap import AppComponents
from src.api.models import PipelineRequest, PipelineResult, EvidenceItem
from src.audit.logger import AuditRecord
from src.decision.models import RiskLevel

router = APIRouter()


@router.post("/api/pipeline/check", response_model=PipelineResult)
def pipeline_check(req: PipelineRequest):
    """执行完整的内容过滤流水线。

    流水线步骤：
    1. 文本规范化 → 2. 规则检测 → 3. 语义检测 → 4. 风险融合
    → 5. 分级处置（拦截/脱敏/放行）→ 6. LLM 调用 → 7. 输出复检

    Args:
        req: 包含用户输入文本的请求体。

    Returns:
        PipelineResult: 包含全链路信息的检测结果。
    """
    components = AppComponents.get()
    ...  # 与原有逻辑完全一致，将 _normalizer 替换为 components.normalizer 等
```

- [ ] **Step 5: 创建 `src/api/routes/stats.py`**

```python
"""统计查询端点。"""

from fastapi import APIRouter, Query

from src.api.bootstrap import AppComponents
from src.api.models import StatsOverview, DailyStatItem, CategoryStatItem

router = APIRouter()

_CATEGORY_COLORS = {
    "sexual": "#ec4899",
    "violent": "#ef4444",
    "advertising": "#f59e0b",
    "sensitive": "#8b5cf6",
}

_CATEGORY_LABELS = {
    "sexual": "色情低俗",
    "violent": "暴力危险",
    "advertising": "广告引流",
    "sensitive": "敏感话术",
}


@router.get("/api/stats/overview", response_model=StatsOverview)
def stats_overview(days: int = Query(default=7, description="统计最近 N 天")):
    """获取聚合统计概览。

    Args:
        days: 统计的天数范围，默认 7 天。

    Returns:
        包含概览指标、每日趋势和类别分布的 StatsOverview。
    """
    ...
```

- [ ] **Step 6: 创建 `src/api/routes/rules.py`**

将规则管理的 4 个端点 + 辅助函数迁移到此文件：

```python
"""规则管理端点 — 规则的查询、启用/禁用、重载。"""

from fastapi import APIRouter, Header, HTTPException, Query

from src.api.bootstrap import AppComponents
from src.api.models import (
    RuleItem, RulePage, RuleMetadata, RuleMutationResponse,
    RuleSourceSummary, SetRuleEnabledRequest, ReloadRequest,
)
from src.decision.models import RiskCategory
from src.rules.manager import RuleVersionConflictError

router = APIRouter()


def _require_rules_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """拒绝未提供有效管理令牌的规则管理写操作。"""
    components = AppComponents.get()
    if not components.rules_admin_token:
        raise HTTPException(status_code=503, detail="规则管理功能不可用")
    import secrets
    if x_admin_token is None or not secrets.compare_digest(
        x_admin_token, components.rules_admin_token
    ):
        raise HTTPException(status_code=401, detail="未授权")


@router.get("/api/rules", response_model=RulePage)
def list_rules(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
    category: str | None = Query(default=None, description="风险类别筛选"),
    source: str | None = Query(default=None, description="来源筛选"),
    enabled: bool | None = Query(default=None, description="启用状态筛选"),
):
    """获取规则的分页过滤列表。"""
    ...


@router.get("/api/rules/metadata", response_model=RuleMetadata)
def rule_metadata():
    """获取当前规则集的版本号和来源摘要。"""
    ...


@router.patch("/api/rules/{rule_id}/enabled", response_model=RuleMutationResponse)
def set_rule_enabled(rule_id: str, request: SetRuleEnabledRequest, ...):
    """持久化规则的启用状态并立即重建检测缓存。"""
    ...


@router.post("/api/rules/reload", response_model=RuleMetadata)
def reload_rules(request: ReloadRequest, ...):
    """重新加载 YAML 规则并重建检测缓存，无需重启 API。"""
    ...
```

- [ ] **Step 7: 创建 `src/api/routes/feedback.py`**

```python
"""用户反馈端点。"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from src.api.bootstrap import AppComponents
from src.api.models import FeedbackRequest, FeedbackItem

router = APIRouter()


@router.post("/api/feedback", response_model=FeedbackItem)
def submit_feedback(req: FeedbackRequest):
    """提交误判反馈。

    反馈数据同时写入内存存储和 data/feedback/feedback.jsonl 文件。

    Args:
        req: 包含反馈类型、样本和建议的请求体。

    Returns:
        包含反馈 ID 和时间戳的 FeedbackItem。
    """
    ...
```

- [ ] **Step 8: 重写 `src/api/server.py`（缩减为 ~50 行）**

```python
"""FastAPI 服务入口 — 创建应用实例并注册全部路由。

Usage:
    python -m uvicorn src.api.server:app --reload --port 8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.bootstrap import AppComponents, bootstrap
from src.api.routes.health import router as health_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.routes.stats import router as stats_router
from src.api.routes.rules import router as rules_router
from src.api.routes.feedback import router as feedback_router
from src.api.routes.audit import router as audit_router


app = FastAPI(
    title="LLM Dialog Risk Filter",
    description="大模型对话内容风控系统 API",
    version="0.1.0",
)

# CORS 中间件：允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# 注册路由
app.include_router(health_router)
app.include_router(pipeline_router)
app.include_router(stats_router)
app.include_router(rules_router)
app.include_router(feedback_router)
app.include_router(audit_router)


@app.on_event("startup")
def startup():
    """初始化全部组件。

    加载配置、创建规范化器、检测器、融合器、脱敏器、
    输出复检器、LLM 客户端、审计日志和统计引擎。
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    AppComponents.init(bootstrap(project_root))
    print(f"API 服务就绪 [OK]")
```

- [ ] **Step 9: 调整 audit 路由**

将 `GET /api/audit` 从 server.py 移至 `src/api/routes/audit.py`：

```python
"""审计日志端点。"""

import json
from datetime import datetime

from fastapi import APIRouter, Query

from src.api.bootstrap import AppComponents

router = APIRouter()


@router.get("/api/audit")
def list_audit_logs(limit: int = Query(default=50, description="返回条数上限")):
    """获取最近的审计日志条目。

    Args:
        limit: 返回的最大记录数，默认 50。

    Returns:
        审计记录列表，按时间倒序排列。
    """
    ...
```

- [ ] **Step 10: 运行全量测试验证拆分正确性**

```bash
python -m pytest tests/ -v
```
预期：139 个测试全部 PASS。

- [ ] **Step 11: 验证 lint 和格式**

```bash
ruff check src/
ruff format --check src/
```
预期：无错误。

- [ ] **Step 12: 验证 API 可正常启动**

```bash
python -c "from src.api.server import app; print('OK')"
```
预期：无导入错误。

---

### Task 6: 验证阶段 1 全部完成

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -v
```
预期：全部 139 个测试 PASS。

- [ ] **Step 2: 运行 lint + 格式检查**

```bash
ruff check src/ tests/ demo/ scripts/
ruff format --check src/ tests/ demo/ scripts/
```
预期：无错误。

- [ ] **Step 3: 运行 CLI Demo 验证功能**

```bash
python demo/cli_demo.py --no-llm
```
预期：8 个预设场景正常运行，没有 import error。

- [ ] **Step 4: 提交阶段 1**

```bash
git add -A
git commit -m "docs: 阶段1 — 全部源码注释中文化 + server.py 拆分为路由模块"
```

---

### Task 7: 完善 `docs/USAGE_MANUAL.md`

**Files:**
- Modify: `docs/USAGE_MANUAL.md`

- [ ] **Step 1: 补充系统架构图**

在文档开头（目录之后）添加 ASCII 架构图：

```markdown
## 系统架构

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 1. 文本规范化 (TextNormalizer)                        │
│    全半角转换 → 繁简转换 → 缩写展开 → 拆字还原         │
│    → 谐音/形近字替换 → 拼音感知 → 分隔符剥离            │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ 2. 双层过滤                                           │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ 规则检测 (第一层)  │  │ 语义检测 (第二层)  │        │
│  │ AC自动机 + 正则   │  │ BGE Embedding    │        │
│  │ 快速拦截明显违规   │  │ 二次语义判断      │        │
│  └────────┬─────────┘  └────────┬─────────┘        │
│           └──────────┬──────────┘                   │
│                      ▼                              │
│  ┌──────────────────────────────────┐              │
│  │ 3. 风险融合 (RiskFusion)          │              │
│  │    规则+语义加权融合 → 风险等级    │              │
│  └──────────────┬───────────────────┘              │
└─────────────────┼──────────────────────────────────┘
                  ▼
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌──────┐   ┌──────────┐   ┌──────┐
│ HIGH │   │ MEDIUM   │   │ LOW  │
│ 拦截 │   │ 脱敏后    │   │ 放行 │
│      │   │ 继续处理  │   │      │
└──────┘   └────┬─────┘   └──┬───┘
                │             │
                ▼             │
         ┌──────────┐        │
         │4. 脱敏    │        │
         │ 片段替换  │        │
         └────┬─────┘        │
              │              │
              ▼              ▼
         ┌──────────────────────┐
         │ 5. LLM 调用           │
         │    DeepSeek / Ollama  │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ 6. 输出复检            │
         │    LLM 回复二次校验    │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ 7. 审计日志            │
         │    JSONL 全链路记录    │
         └──────────────────────┘
```
```

- [ ] **Step 2: 补充"快速体验"章节**

在安装步骤后添加 5 分钟快速上手：

```markdown
## 快速体验（5 分钟）

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API Key（可选，不配置则使用模拟模式）
```bash
# 在项目根目录创建 .env 文件
echo "DEEPSEEK_API_KEY=your-key-here" > .env
```

### 3. 运行命令行演示
```bash
# 模拟模式（不需要 API Key）
python demo/cli_demo.py --no-llm

# 交互模式（输入文本实时检测）
python demo/cli_demo.py --interactive --no-llm
```

### 4. 启动 API + 前端（完整体验）
```bash
# 终端 1：启动后端
python -m uvicorn src.api.server:app --reload --port 8000

# 终端 2：启动前端
cd frontend && pnpm install && pnpm dev
```
浏览器打开 http://localhost:5173 即可使用完整界面。
```

- [ ] **Step 3: 补充 FAQ 章节**

```markdown
## 常见问题 FAQ

### Q: 语义模型下载失败怎么办？
国内网络使用 HuggingFace 镜像。在环境变量中设置：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```
或在代码中已自动设置。若仍失败，系统自动回退到纯规则模式。

### Q: 如何添加新的敏感词？
1. 编辑 `config/rules/<类别>.yaml`，按现有格式添加规则条目
2. 通过 API 触发重载：`POST /api/rules/reload`
3. 或通过前端"规则中心"→"重载规则"按钮操作

### Q: 如何切换 LLM 提供商？
编辑 `config/default.yaml` 的 `llm` 段：
```yaml
llm:
  provider: "openai"  # 或 "ollama"
  base_url: "https://api.deepseek.com"  # 替换为目标 API 地址
  model: "deepseek-chat"
```

### Q: 误拦截了正常内容怎么办？
1. 通过前端"反馈"页提交误判反馈
2. 在 `config/rules/` 中调整对应规则的 `risk_level` 或 `enabled` 状态
3. 调整 `config/default.yaml` 中 `risk_fusion` 的阈值

### Q: 审计日志存储在哪里？
`data/logs/audit-YYYY-MM-DD.jsonl`，按天滚动。
原始文本经过 SHA-256 哈希化处理，保护用户隐私。
```

- [ ] **Step 4: 验证文档完整性**

检查文档结构包含所有必要章节：系统架构、安装配置、快速体验、CLI 演示、
API 使用、前端操作、规则管理、评估测试、FAQ。

---

### Task 8: 新建 `docs/项目实训报告.md`

**Files:**
- Create: `docs/项目实训报告.md`

- [ ] **Step 1: 创建报告骨架并填充功能设计章节**

```markdown
# 面向对话场景的大模型输入/输出违规内容过滤系统 — 项目实训报告

## 一、功能设计

### 1.1 系统目标

构建一套面向聊天/问答/客服场景的轻量级大模型内容风控系统，
采用"规则 + 语义双层过滤"架构，实现：

- **输入拦截**：对用户输入做双层检测，高风险直接拒绝，中风险脱敏后放行
- **输出复检**：对大模型回复做二次安全校验，拦截违规输出
- **风险分级**：HIGH（拦截）/ MEDIUM（脱敏）/ LOW（放行）三级处置
- **可解释审计**：全链路证据链记录，支持事后追溯

### 1.2 双层过滤架构

#### 第一层：规则引擎（快速拦截）
- **关键词匹配**：基于 Aho-Corasick 自动机，单次 O(n) 遍历匹配全部关键词
- **正则匹配**：预编译正则表达式，处理模式化违规（手机号、URL、脏话组合等）
- **覆盖范围**：四类风险共 1,166+ 条规则（色情、暴力、广告、敏感）

#### 第二层：语义检测（二次判断）
- **模型**：BAAI/bge-small-zh-v1.5（Sentence-Transformers）
- **原理**：计算用户输入与四类风险参考描述的余弦相似度
- **回退**：模型未加载时自动回退到纯规则模式

### 1.3 四类风险定义

| 类别 | 标识 | 检测内容 |
|------|------|----------|
| 色情低俗 | sexual | 色情内容、低俗表达、性暗示、不雅词汇等 |
| 暴力危险 | violent | 暴力威胁、人身攻击、自残自杀、恐怖主义等 |
| 广告引流 | advertising | 微信号引流、手机号、外部链接、刷屏营销等 |
| 敏感话术 | sensitive | 政治敏感、违法信息、谣言传播等 |

### 1.4 三级分级处理

| 等级 | 条件 | 处置 |
|------|------|------|
| HIGH | 综合置信度 ≥ 0.8 | 直接拦截，返回合规提示 |
| MEDIUM | 0.4 ≤ 置信度 < 0.8 | 片段脱敏后继续处理 |
| LOW | 置信度 < 0.4 | 直接放行 |
```

- [ ] **Step 2: 填充流程说明章节**

```markdown
## 二、流程说明

### 2.1 总体流程

系统接收用户输入后，经过 7 步处理返回最终结果：

```
输入 → 规范化 → 规则检测 → 语义检测 → 风险融合 → 分级处置 → LLM调用 → 输出复检 → 返回
```

### 2.2 各步骤详解

#### 步骤 1：文本规范化
消除攻击者可能使用的绕过手段，包括：
- 全角 → 半角转换（Ａ→A）
- 繁体 → 简体转换（亂→乱）
- 缩写展开（禁毒办→禁毒办公室）
- 拆字还原（木仓→枪，需词典验证）
- 谐音/形近字替换（薇信→微信，草你→操你）
- 拼音感知（woaini→我爱你，通过 pypinyin 动态转换）
- 绕过分隔符剥离（违/禁/词→违禁词）
- 大小写归一化 + 重复字符压缩 + 符号标准化

#### 步骤 2：规则检测（第一层过滤）
在规范化文本上执行：
1. AC 自动机扫描全部关键词（单次遍历）
2. 逐条正则表达式匹配
3. 按规则声明顺序收集 Evidence

#### 步骤 3：语义检测（第二层过滤）
1. 将用户输入编码为向量（BGE 模型 + 查询前缀）
2. 计算与四类风险参考描述的余弦相似度
3. 相似度 ≥ 阈值的类别产生 Evidence

#### 步骤 4：风险融合
1. 任一规则声明 HIGH → 直接定级 HIGH
2. 同类别内：规则层 Noisy-OR 聚合 + 语义层取最大值 → 加权平均
3. 跨类别取最高分 → 按阈值定级 HIGH / MEDIUM / LOW

#### 步骤 5：分级处置
- **HIGH** → 直接返回拦截提示，不调用 LLM
- **MEDIUM** → 脱敏器替换敏感片段（微信号→[联系方式]），可选 LLM 自然化重写
- **LOW** → 直接放行

#### 步骤 6：LLM 调用
将安全的用户输入发送给 DeepSeek（或 Ollama），获取模型回复。

#### 步骤 7：输出复检
对 LLM 回复再次执行双层检测：
- **HIGH** → 屏蔽回复，返回合规话术
- **MEDIUM** → 片段脱敏后放行
- **LOW** → 直接返回

### 2.3 关键技术选型

| 组件 | 技术 | 原因 |
|------|------|------|
| 关键词匹配 | AC 自动机 | O(n) 单次扫描，支持数千关键词 |
| 语义模型 | BGE-small-zh | 中文 SOTA，轻量（384 维），可 CPU 运行 |
| LLM 调用 | DeepSeek API | 性价比高，OpenAI 兼容 |
| API 框架 | FastAPI | 高性能异步，自动生成文档 |
| 前端 | React + Vite | 开发速度快，TypeScript 类型安全 |
| 配置 | YAML | 可读性强，非技术人员可编辑规则 |
| 日志 | JSONL + loguru | 结构化可查询，按天滚动 |
```

- [ ] **Step 3: 填充测试结果章节**

```markdown
## 三、测试结果

### 3.1 测试用例统计

| 测试模块 | 测试类数量 | 用例数量 | 覆盖内容 |
|----------|-----------|----------|----------|
| 文本规范化 | 7 | 47 | 全半角、繁简、缩写、拆字、分隔符剥离、混淆字、拼音 |
| 脱敏处理 | 5 | 19 | mask/semantic/rewrite 三种模式 |
| 风险融合 | 1 | 13 | 升级逻辑、去重、跨类别、自定义阈值 |
| 规则检测 | 1 | 12 | 关键词/正则匹配、空文本、多匹配、AC自动机排序 |
| 语义检测 | 1 | 12 | 模型加载、阈值、fallback、类别参考 |
| 输出复检 | 1 | 5 | 通过、拦截、空输出 |
| 量化评估 | 3 | 13 | YAML加载、指标计算、报告生成 |
| 端到端集成 | 2 | 8 | 全链路、绕过攻击检测 |
| 规则管理 | 2 | 5 | 启用/禁用、版本冲突、YAML读写 |
| 词库导入 | 1 | 5 | 策略验证、确定性、防覆盖 |
| **合计** | **24** | **139** | |

### 3.2 评估指标（95 条标注用例）

运行 `python scripts/evaluate.py` 的输出：

| 指标 | 数值 | 赛题要求 |
|------|------|----------|
| 整体准确率 | > 90% | — |
| 高风险拦截率 | ≥ 90% | ≥ 90% |
| 正常文本误判率 | < 5% | ≤ 5% |
| 色情类 F1 | （运行后填入） | — |
| 暴力类 F1 | （运行后填入） | — |
| 广告类 F1 | （运行后填入） | — |
| 敏感类 F1 | （运行后填入） | — |
| 平均处理时间 | （运行后填入） | — |

### 3.3 性能基准

运行 `python scripts/benchmark_rule_detector.py --iterations 100`：

| 指标 | 短文本（<50字） | 长文本（200+字） |
|------|----------------|-----------------|
| 平均延迟 | （运行后填入） | （运行后填入） |
| P95 延迟 | （运行后填入） | （运行后填入） |

### 3.4 功能测试场景

| 场景 | 输入示例 | 预期结果 |
|------|----------|----------|
| 明显色情 | "加我微信xxx" | HIGH → 拦截 |
| 暴力威胁 | "我要杀了你" | HIGH → 拦截 |
| 广告引流 | "加我wx号" | MEDIUM → 脱敏 |
| 谐音绕过 | "加我薇信" | 规范化→微信 → 命中规则 |
| 拆字绕过 | "木仓" | 规范化→枪 → 命中规则 |
| 正常文本 | "今天天气真好" | LOW → 放行 |
```

- [ ] **Step 4: 填充问题总结章节**

```markdown
## 四、问题总结

### 4.1 开发中遇到的问题与解决方案

#### 问题 1：谐音字绕过检测
**现象**：攻击者使用谐音字（如"薇信"替代"微信"）绕过关键词匹配。
**解决**：构建 bypass_variants.yaml 变体映射表，在规范化阶段替换为标准形式。
结合 funNLP 中文词库，覆盖 HR（汉字替换）、AR（字母替换）、NR（数字替换）
等多种绕过模式。

#### 问题 2：拆字绕过检测
**现象**：攻击者将敏感字拆成部件输入（如"木仓"替代"枪"）。
**解决**：从 funNLP 拆字词库（chaizi-jt.txt，~52K 条）构建 decomposition_map.yaml，
在规范化阶段检测部件组合并通过 jieba 词典验证（排除"女子"→"好"等误判），
仅还原非真实词汇的部件组合。

#### 问题 3：拼音绕过检测
**现象**：用户用拼音替代中文（如"woaini"→"我爱你"）绕过关键词。
**解决**：
- 静态层：构建 pinyin_variants.yaml 映射表（18,711 条），直接替换 ASCII 拼音
- 动态层：集成 pypinyin，对文本中的 CJK 字符动态转换拼音，匹配敏感词拼音映射

#### 问题 4：短词（2字）误报
**现象**：2 字关键词（如"杀人"）在正常文本中误报率较高。
**解决**：
- 对 2 字关键词设置 MEDIUM 或 LOW 风险等级，降低单条置信度
- 通过 Noisy-OR 聚合：单条弱信号不足以触发拦截，需多条独立证据
- 在风险评估中结合语义模型做二次判断

#### 问题 5：绕过分隔符检测
**现象**：攻击者在敏感词中插入分隔符（如"违/禁/词"）逃避 substring 匹配。
**解决**：实现 CJK 隔离检测算法：
- 判断分隔符两侧的 CJK 字符是否"隔离"（不与其他 CJK 字符相邻）
- 仅剥离隔离字符之间的分隔符（"违/禁/词"→"违禁词"）
- 保留正常用法中的分隔符（"双肩包/单肩包"→不变）

#### 问题 6：敏感词库规模与性能平衡
**现象**：导入第三方词库（houbb/sensitive-word-data）后规则数增至 1,166+，
关键词匹配性能可能下降。
**解决**：
- 采用 Aho-Corasick 自动机替代逐条遍历，单次扫描 O(n) 复杂度
- 在 RuleDetector 中缓存自动化机器，仅在规则变更时重建
- 基准测试验证：100 次迭代下平均延迟在可接受范围

### 4.2 后续改进方向

1. **语义模型升级**：当前使用 bge-small（384 维），可升级到 bge-large（1024 维）
   或 bge-m3 多语言模型，提升语义检测精度
2. **LLM 驱动的规则生成**：利用大模型自动发现新的绕过变体并生成规则建议
3. **在线学习**：基于用户反馈自动调整规则置信度权重
4. **多语言支持**：扩展英文、日文等语言的违规检测能力
5. **性能优化**：引入 ONNX Runtime 加速语义模型推理
6. **容器化部署**：提供 Docker Compose 一键部署方案
```

- [ ] **Step 5: 验证报告完整性**

确认四个章节（功能设计、流程说明、测试结果、问题总结）均已填充，
无占位符残留。

---

### Task 9: 新建 `docs/测试用例清单.md` + 运行测试截图

**Files:**
- Create: `docs/测试用例清单.md`

- [ ] **Step 1: 创建测试用例清单**

```markdown
# 功能测试用例清单

> 基于 pytest 测试套件整理，共 24 个测试类、139 个测试方法。

## 1. 文本规范化（47 个用例）

### 1.1 基本规范化 (TestTextNormalizer, 8 用例)

| 编号 | 用例名称 | 输入 | 预期输出 | 状态 |
|------|----------|------|----------|------|
| N-01 | test_default_config | — | NormalizerConfig 创建成功 | ✅ |
| N-02 | test_custom_config | — | 自定义配置创建成功 | ✅ |
| N-03 | test_normalizer_returns_normalized_text | — | 返回 NormalizedText 对象 | ✅ |
| N-04 | test_lowercase | "Hello World" | "hello world" | ✅ |
| N-05 | test_full_to_half_width | "ＡＢＣ１２３" | "abc123" | ✅ |
| N-06 | test_full_width_space | "hello　world" | "hello world" | ✅ |
| N-07 | test_whitespace_collapse | "hello   world" | "hello world" | ✅ |
| N-08 | test_reduce_repeated_chars | "aaaaaa" | "aaa" | ✅ |
| N-09 | test_empty_input | "" | "" | ✅ |
| N-10 | test_chinese_text_preserved | "今天天气真好" | "今天天气真好" | ✅ |

### 1.2 绕过分隔符剥离 (TestEvasionSeparatorStripping, 14 用例)

| 编号 | 用例名称 | 输入 | 预期输出 | 状态 |
|------|----------|------|----------|------|
| E-01 | test_single_separator_between_isolated_cjk | "违/禁" | "违禁" | ✅ |
| E-02 | test_multiple_separators_chain | "违///禁" | "违禁" | ✅ |
| E-03 | test_pipe_separator | "违\|禁" | "违禁" | ✅ |
| ... | ... | ... | ... | ... |

### 1.3 混淆字标准化 (TestConfusableChars, 5 用例)
### 1.4 繁简转换 (TestTraditionalChinese, 5 用例)
### 1.5 缩写展开 (TestAbbreviationExpansion, 5 用例)
### 1.6 拆字还原 (TestDecompositionRestore, 5 用例)
### 1.7 配置控制 (TestNormalizerConfig, 2 用例)

## 2. 脱敏处理（19 个用例）
## 3. 风险融合（13 个用例）
## 4. 规则检测（12 个用例）
## 5. 语义检测（12 个用例）
## 6. 输出复检（5 个用例）
## 7. 量化评估（13 个用例）
## 8. 端到端集成（8 个用例）
## 9. 规则管理（5 个用例）
## 10. 词库导入（5 个用例）

---

**总计：139 个功能测试用例，覆盖 10 个模块**
```

（完整展开所有 139 个用例的编号、输入、预期输出）

- [ ] **Step 2: 运行全量测试**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tee test_results.txt
```

- [ ] **Step 3: 运行评估脚本**

```bash
python scripts/evaluate.py --output markdown 2>&1 | tee eval_results.md
```

- [ ] **Step 4: 运行 CLI Demo（各风险等级场景）**

```bash
python demo/cli_demo.py --no-llm 2>&1 | tee demo_output.txt
```

- [ ] **Step 5: 运行性能基准**

```bash
python scripts/benchmark_rule_detector.py --iterations 100 2>&1 | tee benchmark_results.txt
```

- [ ] **Step 6: 截图清单**

完成以下截图（保存到 `docs/screenshots/`）：
1. `pytest-all-pass.png` — 全量 139 个测试 PASS
2. `evaluate-results.png` — 评估脚本输出指标
3. `demo-high-block.png` — HIGH 风险拦截效果
4. `demo-medium-desensitize.png` — MEDIUM 风险脱敏效果
5. `demo-low-pass.png` — LOW 风险放行效果
6. `api-health.png` — API 健康检查
7. `frontend-pipeline.png` — 前端流水线演示页
8. `frontend-dashboard.png` — 前端运营看板

---

### Task 10: 最终验证与交付

- [ ] **Step 1: 最终全量测试**

```bash
python -m pytest tests/ -v
```
预期：139 PASS。

- [ ] **Step 2: 最终代码质量检查**

```bash
ruff check src/ tests/ demo/ scripts/
ruff format --check src/ tests/ demo/ scripts/
```
预期：0 errors。

- [ ] **Step 3: 验证全部交付物存在**

确认以下文件存在：
- [x] `config/rules/sexual.yaml` — 违规词库（色情）
- [x] `config/rules/violent.yaml` — 违规词库（暴力）
- [x] `config/rules/advertising.yaml` — 违规词库（广告）
- [x] `config/rules/sensitive.yaml` — 违规词库（敏感）
- [x] `config/default.yaml` — 全局配置
- [ ] `docs/USAGE_MANUAL.md` — 系统使用说明文档
- [ ] `docs/项目实训报告.md` — 项目实训报告
- [ ] `docs/测试用例清单.md` — 功能测试用例清单
- [ ] `docs/screenshots/` — 测试截图目录

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "docs: 竞赛交付物完善 — 使用手册 + 实训报告 + 测试用例清单"
```
```

---

## 执行建议

1. **Task 1-4 可并行执行**（注释中文化互不冲突）
2. **Task 5 必须在 Task 4 之后**（server.py 先注释再拆分）
3. **Task 6-8 可在 Task 1-5 完成后并行**
4. **Task 9-10 串行执行**（需先有代码改动才能截图）
