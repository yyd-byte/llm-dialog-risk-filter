# 后端编码规范

本文件约束 `src/` `demo/` `tests/` `scripts/` 下所有 Python 代码的风格与结构，确保多人协作时代码一致、可读、可维护。

---

## 1. 语言与编码

- Python 3.10+（允许 `str | None` 联合类型语法，不写 `Optional[str]`）
- 文件头 `# -*- coding: utf-8 -*-` 不强制（Python 3 默认 UTF-8）
- 行尾符 LF（`\n`），不要在 Windows 下提交 CRLF

## 2. 行宽与换行

- 硬上限 **100 字符**（非 PEP 8 的 79），docstring 同样适用
- 函数签名过长时，左括号后换行，参数每个一行：

```python
def evaluate(
    self,
    rule_evidence: list[Evidence],
    semantic_evidence: list[Evidence] | None = None,
) -> RiskResult:
    ...
```

- 链式调用过长时，用括号包裹后换行，点号放在行首：

```python
result = (
    self._rules.get(category, [])
    .filter(enabled=True)
    .sort_by_priority()
)
```

## 3. 引号

- **双引号** `"` 用于面向用户的字符串（docstring、日志、错误消息、UI 文案）
- **单引号** `'` 用于内部标识符（字典 key、枚举值、配置键）
- 三引号 `"""..."""` 统一用双引号

```python
# ✅
key = "risk_level"
print(f"风险等级: {value}")
raise RuleLoadError(f"规则目录不存在: {rules_dir}")

# ❌
key = 'risk_level'   # 内部标识, 应用单引号
print(f'风险等级: {value}')  # 面向用户, 应用双引号
```

## 4. 命名

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `rule_detector.py` |
| 类 | `PascalCase` | `RiskFusion`, `AuditLogger` |
| 函数/方法 | `snake_case` | `evaluate_input()`, `load_all()` |
| 变量 | `snake_case` | `rule_evidence`, `max_retry` |
| 常量 | `UPPER_SNAKE` | `DEFAULT_BLOCK_MESSAGE` |
| 私有成员 | 前缀 `_` | `_rebuild_cache()`, `_config` |
| 布尔变量 | `is_` / `has_` / `should_` 前缀 | `is_safe`, `has_evidence` |

- 不用单字母变量（循环变量 `i` `k` `v` 除外）
- 不用拼音，不用中文变量名

## 5. 类型注解

- **所有公开函数/方法必须有完整类型注解**（参数 + 返回值）
- 私有方法可省略，但鼓励注解
- 允许 `X | None` 语法（Python 3.10+），不用 `Optional[X]`
- 容器类型用小写 `list` `dict` `tuple`（Python 3.9+），不用 `List` `Dict` `Tuple`

```python
# ✅
def get_rules(self, category: RiskCategory | None = None) -> list[Rule]:
    ...

# ❌
from typing import Optional, List
def get_rules(self, category: Optional[RiskCategory] = None) -> List[Rule]:
    ...
```

- dataclass 字段必须注解（类型错误在运行时不会报，但 mypy/pyright 会检查）

## 6. 导入顺序

分四组，组间空一行：

1. 标准库 `import os, from pathlib import Path`
2. 第三方库 `import yaml, from pydantic import BaseModel`
3. 项目内部 `from src.decision.models import RiskLevel`
4. 类型检查块 `if TYPE_CHECKING: ...`

每组内按字母序排列。不用 `from module import *`。

```python
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import yaml

from src.decision.models import Evidence, RiskLevel
from src.utils.exceptions import RuleLoadError

if TYPE_CHECKING:
    from transformers import PreTrainedModel
```

## 7. Docstring 规范

### 模块级

每个 `.py` 文件**必须**有模块级 docstring（一句话说明职责）：

```python
"""Rule-based detection engine — keyword and regex matching."""
```

### 类级

公开类**必须**有 docstring，说明职责和设计意图：

```python
class RiskFusion:
    """Fuses rule-based and semantic detection results into a unified risk level.

    Produces an explainable evidence chain showing why each decision was made.
    """
```

### 函数/方法级

公开方法**必须**有 docstring。格式：

```python
def detect(self, text: str) -> list[Evidence]:
    """Run rule-based detection on normalized text.

    Args:
        text: Normalized input text (lowercased, half-width).

    Returns:
        List of Evidence objects, one per matched rule.
        Empty list if nothing matched.

    Raises:
        DetectionError: If the detection pipeline fails unexpectedly.
    """
```

- 第一行用英文祈使句描述行为（"Run..." "Load..." "Create..."）
- `Args` / `Returns` / `Raises` 按需出现，不强制全部
- 私有方法可省略 docstring，但复杂逻辑建议加注释

## 8. 注释

- 注释写中文，面向中文开发者
- 行内注释与代码至少空 2 格
- 不用废话注释（如 `# 调用函数` 后面跟 `foo()`）
- 复杂逻辑、边界条件、临时方案必须注释原因

```python
# ✅
# 全角空格 U+3000 → 半角空格 U+0020
if code == 0x3000:
    result.append(" ")

# 语义模型未加载时回退到纯规则模式，不抛异常
if not self._is_loaded:
    return []

# ❌
# 调用 detect 方法
result = self.detect(text)
```

## 9. 数据类（dataclass）

- 模型/配置/DTO 统一使用 `@dataclass`
- 不要用 `@dataclass` 写有复杂行为的类（业务逻辑类用普通 class）
- 有默认值的字段必须在无默认值字段之后
- 可变默认值用 `field(default_factory=...)`

```python
@dataclass
class RiskResult:
    risk_level: RiskLevel
    risk_category: RiskCategory | None = None
    confidence: float = 0.0
    evidence_chain: list[Evidence] = field(default_factory=list)
```

## 10. 异常处理

- 项目自定义异常统一放在 `src/utils/exceptions.py`
- 自定义异常继承 `RiskFilterError`（基类）
- 捕获异常时指定具体类型，不用裸 `except:`
- 捕获后要么处理，要么转换后重新抛出，**禁止静默吞掉**

```python
# ✅
try:
    data = yaml.safe_load(f)
except yaml.YAMLError as e:
    raise RuleLoadError(f"YAML 解析失败: {filepath}") from e

# ❌
try:
    data = yaml.safe_load(f)
except:
    pass
```

- 库函数不直接 `print()` 错误，用 `raise` 或 `logging`
- 顶层（cli_demo / dashboard）可以 `print()` 友好提示

## 11. 日志

- 日志统一用 `loguru`（`from loguru import logger`）
- 不用 `print()` 做调试输出
- 日志级别：`DEBUG`（开发调试）`INFO`（关键流程）`WARNING`（降级/回退）`ERROR`（可恢复错误）

```python
logger.info(f"规则加载完成，共 {count} 条")
logger.warning("语义模型未加载，回退到纯规则模式")
logger.error(f"LLM 调用失败: {err}")
```

## 12. 配置

- 所有可调参数走 `config/default.yaml`，不硬编码在代码里
- 配置读取在入口处一次性完成，通过构造函数注入，不在模块内部读文件
- 配置类用 `@dataclass`，有合理默认值

```python
# ✅ 入口处读取，注入
config = yaml.safe_load(open("config/default.yaml"))
llm_client = LLMClient(LLMConfig(
    base_url=config["llm"]["base_url"],
    model=config["llm"]["model"],
))

# ❌ 模块内部直接读文件
class LLMClient:
    def __init__(self):
        config = yaml.safe_load(open("config/default.yaml"))  # 不要这样
```

## 13. 测试

- 测试文件放在 `tests/`，命名 `test_<模块名>.py`
- 测试类命名 `Test<被测类名>`，测试方法命名 `test_<场景描述>`
- 每个模块至少覆盖：正常路径、边界条件、错误路径
- 使用 `conftest.py` 中的 fixture，不重复造轮子
- 断言必须带错误消息（pytest 会自动显示，但关键断言加注释）

```python
class TestNormalizer:
    def test_full_width_to_half_width(self, normalizer):
        result = normalizer.normalize("ＡＢＣ１２３")
        assert result.normalized == "abc123"

    def test_empty_input(self, normalizer):
        result = normalizer.normalize("")
        assert result.normalized == ""

    def test_repeated_char_reduction(self, normalizer):
        result = normalizer.normalize("aaaaaaabcdef")
        assert "aaaa" not in result.normalized
```

## 14. 目录与文件

- `src/` 下每个子包有 `__init__.py`，可以空但必须存在
- 每个文件只做一件事（单一职责），超过 300 行考虑拆分
- `__init__.py` 中可以 re-export 常用符号，方便外部导入：

```python
# src/detection/__init__.py
from src.detection.normalizer import TextNormalizer
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
```

## 15. 杂项

- 字符串格式化优先用 **f-string**，不用 `%` 或 `.format()`
- 路径拼接用 `pathlib.Path`，不用 `os.path`
- 文件操作用 `with` 语句，确保关闭
- 临时文件用 `tempfile` 模块，不手动建 `/tmp/xxx`
- 字典遍历用 `.items()`，需要索引用 `enumerate()`
- 空值检查用 `is None` / `is not None`，不用 `== None`
- 布尔值比较直接用 `if condition:`，不用 `if condition == True:`
- 命令行的 `argparse` 描述用中文

## 16. 新增模块检查清单

在提交 PR 前确认：

- [ ] 模块有 docstring
- [ ] 公开方法有类型注解 + docstring
- [ ] 新依赖已加入 `requirements.txt`
- [ ] 配置项已加入 `config/default.yaml`
- [ ] 有对应的 `tests/test_xxx.py`
- [ ] 异常使用项目自定义异常类
- [ ] 没有 `print()` 调试残留
- [ ] 没有 TODO 注释（除非有对应的 issue 编号）
- [ ] 导入未使用 `from module import *`
- [ ] `__init__.py` 已更新（如有必要）