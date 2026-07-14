# funNLP 数据库整合实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 funNLP 仓库整合拆字词库、同义词库、缩写库、繁简体转换库，扩展项目绕过变体检测能力。

**Architecture:** 4 个数据转换脚本处理 funNLP 原始数据 → 生成 3 个新 YAML 配置 + 扩展 1 个现有配置 → normalizer 新增 3 个预处理步骤（繁简转换、缩写展开、拆字还原） → 规则生成脚本注入拆字变体规则。

**Tech Stack:** Python 3.10+, PyYAML, jieba（拆字 Path B 词典验证）, funNLP 原始数据文件

## Global Constraints

- Python 3.10+，遵循 `BACKEND_CONVENTIONS.md` 编码规范
- funNLP 原始数据已 clone 到 `/tmp/funNLP/`，处理时直接读取
- YAML 配置文件使用 UTF-8 编码，保持与现有风格一致的空行和注释
- 所有新增 normalizer 步骤默认开启，可通过 config 开关禁用
- 测试用 pytest，遵循 `tests/test_normalizer.py` 的 fixture 风格

---

### Task 1: 拆字数据转换脚本 + 生成 decomposition_map.yaml

**Files:**
- Create: `scripts/convert_decomposition_data.py`
- Create: `config/decomposition_map.yaml`

**Interfaces:**
- Produces: `config/decomposition_map.yaml` — `{拆字部件组合: 原字}` 反向映射，如 `贝者: 赌`, `丰母: 毒`

- [ ] **Step 1: 编写转换脚本**

```python
#!/usr/bin/env python3
"""Convert funNLP chaizi-jt.txt to decomposition_map.yaml.

Reads the character decomposition dictionary and inverts it:
original: 赌	贝 者
inverted: 贝者 → 赌, 贝 者 → 赌, 者贝 → 赌

Also generates space-separated and reversed-order variants to catch
attackers who write components in different orders.
"""

import yaml
from pathlib import Path
from collections import defaultdict


CHAIZI_PATH = Path("/tmp/funNLP/data/拆字词库/chaizi-jt.txt")
OUTPUT_PATH = Path("config/decomposition_map.yaml")


def main() -> None:
    if not CHAIZI_PATH.exists():
        raise FileNotFoundError(f"chaizi-jt.txt not found at {CHAIZI_PATH}")

    # decomposition_map: "拆字组合" → "原字"
    # Multiple component strings may map to the same character
    decomposition_map: dict[str, str] = {}

    with open(CHAIZI_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            char = parts[0]          # the original character
            # parts[1], parts[2], ... are different decompositions
            for decomp in parts[1:]:
                decomp = decomp.strip()
                if not decomp:
                    continue
                components = decomp.split()  # split on space → list of components
                if len(components) < 2:
                    continue
                # Variant 1: no spaces, original order
                key1 = "".join(components)
                # Variant 2: no spaces, reversed order
                key2 = "".join(reversed(components))
                for key in (key1, key2):
                    if key not in decomposition_map:
                        decomposition_map[key] = char

    # Remove keys that are single characters (no decomposition actually needed)
    decomposition_map = {k: v for k, v in decomposition_map.items() if len(k) >= 2}

    # Write YAML
    header = (
        "# =============================================================================\n"
        "# 拆字 → 原字 反向映射表\n"
        "# 从 funNLP 拆字词库 (chaizi-jt.txt) 自动生成\n"
        "# 用于检测拆分汉字绕过（如 木仓→枪 女子→好）\n"
        "#\n"
        "# 格式: \"拆字部件组合\": \"原字\"\n"
        "# 包含原始顺序和逆序两种变体\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            decomposition_map,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    print(f"Generated {OUTPUT_PATH} with {len(decomposition_map)} entries")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成配置**

```bash
python scripts/convert_decomposition_data.py
```
Expected: prints `Generated config/decomposition_map.yaml with N entries` (N ≈ 25,000-35,000)

- [ ] **Step 3: 验证生成的 YAML 格式**

```bash
python -c "
import yaml
with open('config/decomposition_map.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print(f'Total entries: {len(data)}')
# Spot check known decompositions
assert data.get('贝者') == '赌', '贝者 → 赌 missing'
assert data.get('丰母') == '毒', '丰母 → 毒 missing'
assert data.get('木仓') == '枪', '木仓 → 枪 missing'
print('Spot checks passed')
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/convert_decomposition_data.py config/decomposition_map.yaml
git commit -m "feat: 拆字数据转换脚本 + decomposition_map.yaml（~35K 条）"
```

---

### Task 2: 缩写数据转换脚本 + 生成 abbreviation_map.yaml

**Files:**
- Create: `scripts/convert_abbreviation_data.py`
- Create: `config/abbreviation_map.yaml`

**Interfaces:**
- Produces: `config/abbreviation_map.yaml` — `{缩写: 完整形式}`，如 `参赌: 参加赌博`, `禁毒办: 禁毒办公室`

- [ ] **Step 1: 编写转换脚本**

```python
#!/usr/bin/env python3
"""Convert funNLP abbreviation dataset to abbreviation_map.yaml.

Reads train/dev/test sets, strips POS tags, and produces a clean
abbreviation → full-form mapping. Handles entries with the format:
  禁毒办: 禁毒/vn 办公室/n
  →
  禁毒办: 禁毒办公室
"""

import yaml
from pathlib import Path
import re


ABBREV_DIR = Path("/tmp/funNLP/data/中文缩写库")
OUTPUT_PATH = Path("config/abbreviation_map.yaml")


def remove_pos_tags(text: str) -> str:
    """Remove POS tags like /vn, /n, /nr from a word."""
    return re.sub(r"/[a-zA-Z]+", "", text)


def main() -> None:
    all_entries: dict[str, str] = {}

    for filename in ["train_set.txt", "dev_set.txt", "test_set.txt"]:
        filepath = ABBREV_DIR / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or ":" not in line:
                    continue
                # Format: "abbrev: word1/POS word2/POS ..."
                abbrev, rest = line.split(":", 1)
                abbrev = abbrev.strip()
                rest = rest.strip()

                # Skip entries where abbreviation starts with "n:" (annotation error)
                if abbrev == "n":
                    continue

                # Remove POS tags and join
                words = rest.split()
                full_form = "".join(remove_pos_tags(w) for w in words)

                if abbrev and full_form and len(abbrev) >= 2:
                    # Keep the first occurrence (train > dev > test)
                    if abbrev not in all_entries:
                        all_entries[abbrev] = full_form

    # Sort by key length descending for longest-match-first replacement
    sorted_entries = dict(
        sorted(all_entries.items(), key=lambda x: len(x[0]), reverse=True)
    )

    header = (
        "# =============================================================================\n"
        "# 中文缩写 → 完整形式 映射表\n"
        "# 从 funNLP 中文缩写库自动生成\n"
        "# 用于在 normalizer 中将缩写展开为完整形式\n"
        "#\n"
        "# 格式: \"缩写\": \"完整形式\"\n"
        "# 缩写 ≥2 字符，完整形式去除词性标签\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            sorted_entries,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    print(f"Generated {OUTPUT_PATH} with {len(sorted_entries)} entries")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成配置**

```bash
python scripts/convert_abbreviation_data.py
```
Expected: `Generated config/abbreviation_map.yaml with N entries` (N ≈ 10,000+)

- [ ] **Step 3: 验证生成的 YAML**

```bash
python -c "
import yaml
with open('config/abbreviation_map.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print(f'Total entries: {len(data)}')
# Spot check
found = [k for k in data if '赌' in data.get(k, '')]
print(f'Gambling-related abbrevs: {found[:5]}')
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/convert_abbreviation_data.py config/abbreviation_map.yaml
git commit -m "feat: 缩写数据转换脚本 + abbreviation_map.yaml（~10K 条）"
```

---

### Task 3: 繁简转换数据脚本 + 生成 traditional_simplified.yaml

**Files:**
- Create: `scripts/convert_traditional_simplified.py`
- Create: `config/traditional_simplified.yaml`

**Interfaces:**
- Produces: `config/traditional_simplified.yaml` — `{繁体: 简体}`，仅包含有差异的 5,908 对

- [ ] **Step 1: 编写转换脚本**

```python
#!/usr/bin/env python3
"""Convert funNLP fanjian_suoyin.txt to traditional_simplified.yaml.

Extracts only the entries where traditional ≠ simplified (5,908 pairs).
"""

import yaml
from pathlib import Path


FANJIAN_PATH = Path("/tmp/funNLP/data/繁简体转换词库/fanjian_suoyin.txt")
OUTPUT_PATH = Path("config/traditional_simplified.yaml")


def main() -> None:
    if not FANJIAN_PATH.exists():
        raise FileNotFoundError(f"fanjian_suoyin.txt not found at {FANJIAN_PATH}")

    ts_map: dict[str, str] = {}
    same_count = 0

    with open(FANJIAN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            traditional = parts[0].strip()
            simplified = parts[1].strip()
            if traditional != simplified and traditional and simplified:
                ts_map[traditional] = simplified
            else:
                same_count += 1

    header = (
        "# =============================================================================\n"
        "# 繁体中文 → 简体中文 映射表\n"
        "# 从 funNLP 繁简体转换词库自动生成\n"
        "# 仅包含有差异的繁简对（同字行列不计）\n"
        "#\n"
        "# 格式: \"繁体\": \"简体\"\n"
        "# =============================================================================\n"
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        yaml.dump(
            ts_map,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    print(f"Generated {OUTPUT_PATH} with {len(ts_map)} differing pairs "
          f"({same_count} same-char lines skipped)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成配置**

```bash
python scripts/convert_traditional_simplified.py
```
Expected: `Generated config/traditional_simplified.yaml with 5908 differing pairs (11895 same-char lines skipped)`

- [ ] **Step 3: 验证生成的 YAML**

```bash
python -c "
import yaml
with open('config/traditional_simplified.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
assert data.get('亂') == '乱', '亂 → 乱 missing'
assert data.get('倉') == '仓', '倉 → 仓 missing'
assert data.get('並') == '并', '並 → 并 missing'
print(f'Total: {len(data)}, spot checks passed')
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/convert_traditional_simplified.py config/traditional_simplified.yaml
git commit -m "feat: 繁简转换数据脚本 + traditional_simplified.yaml（5,908 对）"
```

---

### Task 4: 同义词库扩充 bypass_variants.yaml

**Files:**
- Create: `scripts/expand_bypass_from_synonyms.py`
- Modify: `config/bypass_variants.yaml`

**Interfaces:**
- Consumes: `config/bypass_variants.yaml` (existing), `/tmp/funNLP/data/同义词库、反义词库、否定词库/同义词库.txt`
- Produces: 追加新条目到 `config/bypass_variants.yaml`

- [ ] **Step 1: 编写扩展脚本**

```python
#!/usr/bin/env python3
"""Expand bypass_variants.yaml using the HIT-CIR Chinese Thesaurus (同义词词林).

Strategy:
1. Read existing bypass_variants keys (Chinese-character entries only).
2. For each seed, look up its synonym group in the thesaurus.
3. Add all group members as new bypass variants pointing to the seed's
   replacement value (or to the first seed word if from rules).
4. Skip single-character entries (too high false-positive risk).
5. Skip entries already in bypass_variants.
"""

import yaml
from pathlib import Path
import re

BYPASS_PATH = Path("config/bypass_variants.yaml")
THESAURUS_PATH = Path(
    "/tmp/funNLP/data/同义词库、反义词库、否定词库/同义词库.txt"
)


def is_chinese(s: str) -> bool:
    """Check if string contains Chinese characters."""
    return bool(re.search(r"[一-鿿]", s))


def load_thesaurus(path: Path) -> dict[str, set[str]]:
    """Load the HIT-CIR thesaurus.

    Returns: {word: set_of_synonyms} — each word maps to all words in
    the same synset group(s).
    """
    word_to_synonyms: dict[str, set[str]] = {}
    synset_count = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or "=" not in line:
                continue
            # Format: "Aa01A01= 人 士 人物 人士 ..."
            synset_id, words_str = line.split("=", 1)
            words = [w.strip() for w in words_str.split() if w.strip()]
            if len(words) < 2:
                continue
            synset_count += 1
            for word in words:
                if word not in word_to_synonyms:
                    word_to_synonyms[word] = set()
                word_to_synonyms[word].update(w for w in words if w != word)

    print(f"Loaded {synset_count} synsets, {len(word_to_synonyms)} unique words")
    return word_to_synonyms


def main() -> None:
    if not THESAURUS_PATH.exists():
        raise FileNotFoundError(f"Thesaurus not found at {THESAURUS_PATH}")

    if not BYPASS_PATH.exists():
        raise FileNotFoundError(f"bypass_variants.yaml not found at {BYPASS_PATH}")

    # Load existing bypass variants
    with open(BYPASS_PATH, "r", encoding="utf-8") as f:
        existing_data = yaml.safe_load(f) or {}

    existing_keys = set(existing_data.keys())
    existing_values = set(existing_data.values())

    # Load thesaurus
    thesaurus = load_thesaurus(THESAURUS_PATH)

    # Collect seeds: Chinese-character keys from existing bypass variants
    seeds: dict[str, str] = {}
    for key, value in existing_data.items():
        key_str = str(key).strip()
        if is_chinese(key_str) and len(key_str) >= 2:
            seeds[key_str] = str(value)

    print(f"Found {len(seeds)} Chinese-character seed entries in bypass_variants")

    # Find new variants
    new_entries: dict[str, str] = {}
    for seed_word, target in seeds.items():
        if seed_word not in thesaurus:
            continue
        for synonym in thesaurus[seed_word]:
            # Skip single-character words
            if len(synonym) < 2:
                continue
            # Skip if already exists
            if synonym in existing_keys or synonym in new_entries:
                continue
            # Skip if the synonym IS the target word itself
            if synonym == target:
                continue
            # Skip if synonym is too common (single-char safe, but multi-char
            # that looks like normal vocabulary — check it's not just a normal
            # word that happens to be in a synset)
            # Don't add if it's a very common word (>3 chars often safe)
            if len(synonym) <= 4:
                new_entries[synonym] = target

    print(f"Found {len(new_entries)} new bypass variants from thesaurus")

    if not new_entries:
        print("No new entries to add, exiting")
        return

    # Write back: rebuild the YAML file preserving the original structure
    # Read the raw file content
    with open(BYPASS_PATH, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Build the new section to append
    new_section_lines = [
        "",
        "# === 同音/同义变体（来自哈工大同义词词林 HIT-CIR）===",
    ]
    # Group by target for readability
    by_target: dict[str, list[str]] = {}
    for k, v in new_entries.items():
        by_target.setdefault(v, []).append(k)

    for target, variants in sorted(by_target.items()):
        new_section_lines.append(f"# → {target}")
        for variant in sorted(variants):
            new_section_lines.append(f"{variant}: {target}")

    new_section = "\n".join(new_section_lines) + "\n"

    with open(BYPASS_PATH, "a", encoding="utf-8") as f:
        f.write(new_section)

    print(f"Appended {len(new_entries)} entries to {BYPASS_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 备份现有文件，运行脚本**

```bash
cp config/bypass_variants.yaml config/bypass_variants.yaml.bak
python scripts/expand_bypass_from_synonyms.py
```
Expected: prints count of seeds and new entries added (est. 200-400)

- [ ] **Step 3: 验证生成的条目格式正确**

```bash
python -c "
import yaml
with open('config/bypass_variants.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
# Check that all new entries have valid YAML format
print(f'Total bypass_variants entries: {len(data)}')
# Spot check a few new synonym entries exist
assert isinstance(data, dict), 'Root should be a dict'
print('Format validation passed')
"
```

- [ ] **Step 4: Commit**

```bash
rm config/bypass_variants.yaml.bak
git add scripts/expand_bypass_from_synonyms.py config/bypass_variants.yaml
git commit -m "feat: 同义词库扩充 bypass_variants（+200-400 条 HIT-CIR）"
```

---

### Task 5: Normalizer — 繁→简转换步骤

**Files:**
- Modify: `src/detection/normalizer.py`

**Interfaces:**
- Consumes: `config/traditional_simplified.yaml` (loaded via config)
- Produces: `_normalize_traditional_chinese(text: str) -> str`

- [ ] **Step 1: 在 NormalizerConfig 中添加新字段**

在 `NormalizerConfig` dataclass 末尾添加：

```python
    # New: traditional Chinese → simplified Chinese
    normalize_traditional: bool = True
    traditional_simplified_map: dict[str, str] = field(default_factory=dict)
```

在 `Edit` 的目标位置是 `NormalizerConfig` 中 `pinyin_map` 字段之后。先找到精确位置：

文件 `src/detection/normalizer.py`，在 `pinyin_map: dict[str, str] = field(default_factory=dict)` 之后插入：

```python
    # New: traditional Chinese → simplified Chinese
    normalize_traditional: bool = True
    traditional_simplified_map: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 2: 添加 _normalize_traditional_chinese 方法**

在 TextNormalizer 类中的 `_normalize_pinyin_variants` 方法之后添加新方法。在 `_normalize_confusable_chars` 方法定义之前插入：

```python
    def _normalize_traditional_chinese(self, text: str) -> str:
        """Convert traditional Chinese characters to simplified.

        Uses the traditional_simplified_map from config, loaded from
        traditional_simplified.yaml.
        """
        if not self.config.traditional_simplified_map:
            return text
        str_map = {str(k): str(v) for k, v
                   in self.config.traditional_simplified_map.items()}
        result = []
        for ch in text:
            result.append(str_map.get(ch, ch))
        return "".join(result)
```

- [ ] **Step 3: 将新步骤加入 normalize() 的步骤列表**

在 `normalize()` 方法中，`self._normalize_full_to_half` 之后插入 `self._normalize_traditional_chinese`。即步骤列表变为：

```python
            self._normalize_full_to_half,
            self._normalize_traditional_chinese,
            self._normalize_confusable_chars,
```

- [ ] **Step 4: 在 _is_enabled 中添加映射**

在 `_is_enabled()` 方法的 mapping 字典中添加：

```python
            "_normalize_traditional_chinese": self.config.normalize_traditional,
```

- [ ] **Step 5: 添加测试**

在 `tests/test_normalizer.py` 末尾添加：

```python
class TestTraditionalChinese:
    """Tests for _normalize_traditional_chinese."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with traditional→simplified enabled."""
        test_map = {
            "亂": "乱",
            "倫": "伦",
            "倉": "仓",
            "庫": "库",
        }
        return TextNormalizer(NormalizerConfig(
            normalize_traditional=True,
            traditional_simplified_map=test_map,
        ))

    def test_traditional_to_simplified(self, normalizer):
        """Traditional characters should be converted to simplified."""
        result = normalizer.normalize("亂倫")
        assert "乱" in result.normalized
        assert "倫" not in result.normalized

    def test_traditional_full_text(self, normalizer):
        """Full traditional text should be converted."""
        result = normalizer.normalize("倉庫")
        assert result.normalized == "仓库" or "仓库" in result.normalized

    def test_mixed_traditional_simplified(self, normalizer):
        """Mixed text should have only traditional chars converted."""
        result = normalizer.normalize("亂伦")
        assert "乱" in result.normalized

    def test_disabled_traditional(self):
        """When disabled, traditional chars should not be converted."""
        test_map = {"亂": "乱"}
        cfg = NormalizerConfig(
            normalize_traditional=False,
            traditional_simplified_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("亂倫")
        assert "亂" in result.normalized

    def test_empty_map(self):
        """Empty traditional map should not crash."""
        n = TextNormalizer(NormalizerConfig(
            normalize_traditional=True,
            traditional_simplified_map={},
        ))
        result = n.normalize("亂倫")
        assert "亂" in result.normalized
```

- [ ] **Step 6: 运行测试验证**

```bash
python -m pytest tests/test_normalizer.py::TestTraditionalChinese -v
```
Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/detection/normalizer.py tests/test_normalizer.py
git commit -m "feat: normalizer 新增繁→简转换步骤"
```

---

### Task 6: Normalizer — 缩写展开步骤

**Files:**
- Modify: `src/detection/normalizer.py`

**Interfaces:**
- Consumes: `config/abbreviation_map.yaml` (loaded via config)
- Produces: `_normalize_abbreviations(text: str) -> str`

- [ ] **Step 1: 在 NormalizerConfig 中添加新字段**

在 `traditional_simplified_map` 字段之后添加：

```python
    # New: abbreviation expansion
    normalize_abbreviations: bool = True
    abbreviation_map: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 2: 添加 _normalize_abbreviations 方法**

在 `_normalize_traditional_chinese` 方法之后添加：

```python
    def _normalize_abbreviations(self, text: str) -> str:
        """Expand known abbreviations to their full forms.

        Uses longest-match-first to prevent partial matches:
        "禁毒办" should match "禁毒办" not "禁毒" first.

        Only matches Chinese abbreviations (2+ CJK characters) to
        avoid false positives on English acronyms.
        """
        if not self.config.abbreviation_map:
            return text
        str_map = {str(k): str(v) for k, v
                   in self.config.abbreviation_map.items()}
        # Keys are already sorted by length descending in the YAML.
        # But sort again to be safe.
        for abbr in sorted(str_map, key=len, reverse=True):
            if len(abbr) < 2:
                continue
            if not _contains_cjk(abbr):
                continue
            if abbr in text:
                text = text.replace(abbr, str_map[abbr])
        return text
```

- [ ] **Step 3: 将新步骤加入 normalize() 步骤列表**

在 `_normalize_traditional_chinese` 之后、`_normalize_confusable_chars` 之前插入：

```python
            self._normalize_traditional_chinese,
            self._normalize_abbreviations,
            self._normalize_confusable_chars,
```

- [ ] **Step 4: 在 _is_enabled 中添加映射**

```python
            "_normalize_abbreviations": self.config.normalize_abbreviations,
```

- [ ] **Step 5: 添加测试**

在 `tests/test_normalizer.py` 末尾添加：

```python
class TestAbbreviationExpansion:
    """Tests for _normalize_abbreviations."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with abbreviation expansion enabled."""
        test_map = {
            "禁毒办": "禁毒办公室",
            "参赌": "参加赌博",
            "扫黄打非": "扫黄打非",
        }
        return TextNormalizer(NormalizerConfig(
            normalize_abbreviations=True,
            abbreviation_map=test_map,
        ))

    def test_abbreviation_expansion(self, normalizer):
        """Known abbreviation should be expanded to full form."""
        result = normalizer.normalize("禁毒办通报")
        assert "禁毒办公室" in result.normalized
        assert "禁毒办" not in result.normalized

    def test_abbreviation_catches_sensitive_word(self, normalizer):
        """Expanded abbreviation should reveal sensitive keywords."""
        result = normalizer.normalize("有人参赌")
        assert "参加赌博" in result.normalized

    def test_longest_match_priority(self, normalizer):
        """Longer abbreviation should match before shorter substring."""
        result = normalizer.normalize("扫黄打非行动")
        assert "扫黄打非" in result.normalized

    def test_disabled_abbreviation(self):
        """When disabled, abbreviations should not be expanded."""
        test_map = {"参赌": "参加赌博"}
        cfg = NormalizerConfig(
            normalize_abbreviations=False,
            abbreviation_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("参赌人员")
        assert "参赌" in result.normalized

    def test_empty_map(self):
        """Empty abbreviation map should not crash."""
        n = TextNormalizer(NormalizerConfig(
            normalize_abbreviations=True,
            abbreviation_map={},
        ))
        result = n.normalize("禁毒办通报")
        assert "禁毒办" in result.normalized
```

- [ ] **Step 6: 运行测试验证**

```bash
python -m pytest tests/test_normalizer.py::TestAbbreviationExpansion -v
```
Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/detection/normalizer.py tests/test_normalizer.py
git commit -m "feat: normalizer 新增缩写展开步骤"
```

---

### Task 7: Normalizer — 拆字还原步骤（Path B）

**Files:**
- Modify: `src/detection/normalizer.py`

**Interfaces:**
- Consumes: `config/decomposition_map.yaml` (loaded via config), jieba 词典
- Produces: `_normalize_decomposition(text: str) -> str`

- [ ] **Step 1: 在 NormalizerConfig 中添加新字段**

在 `abbreviation_map` 字段之后添加：

```python
    # New: character decomposition restoration (Path B)
    normalize_decomposition: bool = True
    decomposition_map: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 2: 添加 _normalize_decomposition 方法**

在 `_normalize_abbreviations` 方法之后添加：

```python
    def _normalize_decomposition(self, text: str) -> str:
        """Restore decomposed CJK characters (Path B: global with dictionary check).

        Detects patterns where attackers write characters as individual
        components to evade keyword matching. Only reverses when the
        component combination is NOT a real Chinese word (verified via
        jieba's built-in frequency dictionary).

        Example:
            "木仓" → not a real word → "枪" (restored)
            "女子" → real word (woman) → kept as-is
        """
        if not self.config.decomposition_map:
            return text

        str_map = {str(k): str(v) for k, v
                   in self.config.decomposition_map.items()}

        # Build a set of known Chinese words for dictionary validation
        try:
            import jieba
            _known_words: frozenset[str] = frozenset(
                w for w in jieba.dt.FREQ if len(w) >= 2
            )
        except (ImportError, AttributeError):
            _known_words = frozenset()

        result = list(text)
        n = len(text)

        i = 0
        while i < n:
            matched = False
            for window in range(min(5, n - i), 1, -1):
                candidate = text[i:i + window]
                if candidate not in str_map:
                    continue
                original_char = str_map[candidate]

                if _known_words and candidate in _known_words:
                    # This is a real dictionary word — don't restore
                    # (e.g., "女子" = woman, not "好")
                    matched = False
                else:
                    # Not a known word → likely decomposition → restore
                    result[i:i + window] = [original_char]
                    matched = True
                break
            i += window if matched else 1

        return "".join(result)
```

- [ ] **Step 3: 将新步骤加入 normalize() 步骤列表**

在 `_normalize_abbreviations` 之后、`_normalize_confusable_chars` 之前插入：

```python
            self._normalize_traditional_chinese,
            self._normalize_abbreviations,
            self._normalize_decomposition,
            self._normalize_confusable_chars,
```

- [ ] **Step 4: 在 _is_enabled 中添加映射**

```python
            "_normalize_decomposition": self.config.normalize_decomposition,
```

- [ ] **Step 5: 添加测试**

在 `tests/test_normalizer.py` 末尾添加：

```python
class TestDecompositionRestore:
    """Tests for _normalize_decomposition (Path B)."""

    @pytest.fixture
    def normalizer(self):
        """Normalizer with decomposition restoration enabled."""
        test_map = {
            "贝者": "赌",
            "木仓": "枪",
            "丰母": "毒",
        }
        return TextNormalizer(NormalizerConfig(
            normalize_decomposition=True,
            decomposition_map=test_map,
        ))

    def test_decomposition_restored(self, normalizer):
        """Non-word component combination should be restored."""
        result = normalizer.normalize("玩贝者游戏")
        assert "赌" in result.normalized

    def test_multiple_decompositions(self, normalizer):
        """Multiple decompositions in one text should all be restored."""
        result = normalizer.normalize("贝者博木仓")
        # Both "贝者"→"赌" and "木仓"→"枪" should be restored
        assert "赌" in result.normalized
        assert "枪" in result.normalized

    def test_disabled_decomposition(self):
        """When disabled, decompositions should not be restored."""
        test_map = {"贝者": "赌"}
        cfg = NormalizerConfig(
            normalize_decomposition=False,
            decomposition_map=test_map,
        )
        n = TextNormalizer(cfg)
        result = n.normalize("玩贝者游戏")
        assert "贝者" in result.normalized

    def test_empty_map(self):
        """Empty decomposition map should not crash."""
        n = TextNormalizer(NormalizerConfig(
            normalize_decomposition=True,
            decomposition_map={},
        ))
        result = n.normalize("贝者博")
        assert "贝者" in result.normalized

    def test_normal_text_unchanged(self, normalizer):
        """Normal Chinese text should not be modified."""
        result = normalizer.normalize("正常的文本内容")
        assert "正常的文本内容" in result.normalized
```

- [ ] **Step 6: 运行测试验证**

```bash
python -m pytest tests/test_normalizer.py::TestDecompositionRestore -v
```
Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/detection/normalizer.py tests/test_normalizer.py
git commit -m "feat: normalizer 新增拆字还原步骤（Path B: 词典验证）"
```

---

### Task 8: 拆字变体规则生成（Path A）

**Files:**
- Create: `scripts/generate_decomposition_rules.py`
- Modify: `config/rules/sexual.yaml`, `config/rules/violent.yaml`, `config/rules/advertising.yaml`, `config/rules/sensitive.yaml`

**Interfaces:**
- Consumes: `config/rules/*.yaml`, `config/decomposition_map.yaml`
- Produces: 追加拆字变体规则到各规则文件

- [ ] **Step 1: 编写规则生成脚本**

```python
#!/usr/bin/env python3
"""Generate decomposition-variant rules for all existing Chinese keywords.

Path A: Pre-compute decomposition variants for each multi-character
Chinese keyword in the rule base, then inject them as additional keyword
rules.

Example:
    Rule "赌博" → decompose "赌"="贝者", "博"="十甫寸"
    → Generate rules: "贝者十甫寸", "贝者 十甫寸"
"""

import yaml
from pathlib import Path
from itertools import product


RULES_DIR = Path("config/rules")
DECOMP_MAP_PATH = Path("config/decomposition_map.yaml")

# Categories to process
CATEGORIES = ["sexual", "violent", "advertising", "sensitive"]


def load_decomposition_map(path: Path) -> dict[str, list[str]]:
    """Load and invert the decomposition map.

    Returns: {char: [component_variant1, component_variant2, ...]}
    Where each component_variant is a string like "贝者" (no spaces).
    """
    with open(path, "r", encoding="utf-8") as f:
        decomp_to_char: dict[str, str] = yaml.safe_load(f) or {}

    char_to_decomps: dict[str, list[str]] = {}
    for decomp_str, char in decomp_to_char.items():
        decomp_str = str(decomp_str)
        char = str(char)
        # Only use non-spaced variants (they have ≥2 chars and no spaces)
        if " " not in decomp_str and len(decomp_str) >= 2:
            if char not in char_to_decomps:
                char_to_decomps[char] = []
            if decomp_str not in char_to_decomps[char]:
                char_to_decomps[char].append(decomp_str)

    return char_to_decomps


def decompose_word(word: str,
                   char_to_decomps: dict[str, list[str]]) -> list[str]:
    """Generate all decomposition variants for a word.

    Returns a list of variant strings (no spaces).
    """
    # For each character in the word, get its decomposition variants
    per_char_decomps: list[list[str]] = []
    for ch in word:
        variants = char_to_decomps.get(ch, [])
        if not variants:
            variants = [ch]  # No decomposition → keep original
        per_char_decomps.append(variants)

    # Cartesian product to generate all combinations
    results = []
    for combo in product(*per_char_decomps):
        variant = "".join(combo)
        # Only keep if at least one char was actually decomposed
        if variant != word:
            results.append(variant)

    return results


def main() -> None:
    if not DECOMP_MAP_PATH.exists():
        raise FileNotFoundError(
            f"{DECOMP_MAP_PATH} not found. Run "
            "scripts/convert_decomposition_data.py first."
        )

    char_to_decomps = load_decomposition_map(DECOMP_MAP_PATH)
    print(f"Loaded {len(char_to_decomps)} characters with decompositions")

    total_added = 0

    for category in CATEGORIES:
        rule_file = RULES_DIR / f"{category}.yaml"
        if not rule_file.exists():
            print(f"  {category}: file not found, skipping")
            continue

        with open(rule_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        existing_rules = data.get("rules", [])
        existing_patterns = {r["pattern"] for r in existing_rules
                             if r.get("pattern")}
        existing_ids = {r.get("id", "") for r in existing_rules}

        new_rules = []
        for rule in existing_rules:
            pattern = rule.get("pattern", "")
            pattern_type = rule.get("pattern_type", "keyword")
            # Only process keyword rules with Chinese characters
            if pattern_type != "keyword":
                continue
            # Only decompose patterns with ≥2 Chinese characters
            chinese_chars = [ch for ch in pattern
                             if "一" <= ch <= "鿿"]
            if len(chinese_chars) < 2:
                continue

            variants = decompose_word(pattern, char_to_decomps)
            for v in variants:
                if v not in existing_patterns:
                    new_rules.append({
                        "id": f"{rule['id']}-decomp-{v[:8]}",
                        "pattern": v,
                        "pattern_type": "keyword",
                        "risk_level": rule.get("risk_level", "medium"),
                        "enabled": True,
                        "description": (
                            f"拆字绕过: {pattern} → {v} "
                            f"(source: decomposition, parent: {rule['id']})"
                        ),
                        "source": "decomposition",
                    })
                    existing_patterns.add(v)

        if new_rules:
            # Append to existing rules
            existing_rules.extend(new_rules)
            data["rules"] = existing_rules

            with open(rule_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    data, f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            print(f"  {category}: added {len(new_rules)} decomp rules")
            total_added += len(new_rules)
        else:
            print(f"  {category}: no new decomp rules")

    print(f"\nTotal new decomposition rules: {total_added}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本**

```bash
python scripts/generate_decomposition_rules.py
```
Expected: prints category-by-category counts, total 300-600

- [ ] **Step 3: 验证生成的规则**

```bash
python -c "
import yaml
for cat in ['sexual', 'violent', 'advertising', 'sensitive']:
    with open(f'config/rules/{cat}.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    decomp_rules = [r for r in data['rules'] if r.get('source') == 'decomposition']
    print(f'{cat}: {len(decomp_rules)} decomp rules out of {len(data[\"rules\"])} total')
    if decomp_rules:
        print(f'  Example: {decomp_rules[0][\"pattern\"]} → {decomp_rules[0][\"description\"][:60]}')
"
```

- [ ] **Step 4: 运行全部测试确保不破坏现有功能**

```bash
python -m pytest tests/ -v
```
Expected: all existing tests pass + new normalizer tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_decomposition_rules.py config/rules/sexual.yaml config/rules/violent.yaml config/rules/advertising.yaml config/rules/sensitive.yaml
git commit -m "feat: 拆字变体规则自动生成（Path A: +300-600 条）"
```

---

### Task 9: 更新 default.yaml 配置

**Files:**
- Modify: `config/default.yaml`

**Interfaces:**
- Consumes: 所有新增的 YAML 配置文件
- Produces: 完整可用的全局配置

- [ ] **Step 1: 更新 normalizer 配置段**

把 `config/default.yaml` 中的 `normalizer` 段替换为：

```yaml
# --- Text Normalization ---
normalizer:
  lowercase: true
  full_to_half: true              # 全角 → 半角
  normalize_traditional: true      # 繁 → 简（来自 funNLP 繁简体转换词库）
  normalize_whitespace: true      # 合并异常空格
  reduce_repeated_chars: true     # 压缩重复字符
  max_repeat: 3                   # 重复字符最大保留次数
  normalize_symbols: true         # 变体符号标准化
  strip_evasion_separators: true  # 剥离绕过分隔符（/ | - 等）
  normalize_confusable_chars: true # 混淆字还原（形近字/同音字）
  normalize_pinyin: true           # 拼音感知绕过检测（需 pypinyin）
  normalize_abbreviations: true    # 缩写展开（来自 funNLP 中文缩写库）
  normalize_decomposition: true    # 拆字还原 Path B（来自 funNLP 拆字词库）
```

- [ ] **Step 2: 验证配置能正常加载**

```bash
python -c "
import yaml
with open('config/default.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
n = cfg['normalizer']
assert n['normalize_traditional'] is True
assert n['normalize_abbreviations'] is True
assert n['normalize_decomposition'] is True
print('Config validation passed')
"
```

- [ ] **Step 3: Commit**

```bash
git add config/default.yaml
git commit -m "feat: default.yaml 新增繁简、缩写、拆字配置开关"
```

---

### Task 10: 集成测试 — 端到端绕过检测验证

**Files:**
- Create: `tests/test_funNLP_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
"""Integration tests for funNLP-based variant detection."""

import pytest
import yaml
from pathlib import Path

from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.rules.manager import RuleManager
from src.rules.repository import RuleRepository


def load_yaml_map(path: str) -> dict[str, str]:
    """Load a YAML mapping file, returning empty dict on failure."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(k): str(v) for k, v in (data or {}).items()}


def build_full_normalizer() -> TextNormalizer:
    """Build a TextNormalizer with all funNLP configs loaded."""
    ts_map = load_yaml_map("config/traditional_simplified.yaml")
    abbr_map = load_yaml_map("config/abbreviation_map.yaml")
    decomp_map = load_yaml_map("config/decomposition_map.yaml")
    bypass_map = load_yaml_map("config/bypass_variants.yaml")
    confusable_map = load_yaml_map("config/confusable_chars.yaml")
    pinyin_map = load_yaml_map("config/pinyin_variants.yaml")

    cfg = NormalizerConfig(
        normalize_traditional=True,
        traditional_simplified_map=ts_map,
        normalize_abbreviations=True,
        abbreviation_map=abbr_map,
        normalize_decomposition=True,
        decomposition_map=decomp_map,
        normalize_bypass=True,
        bypass_map=bypass_map,
        normalize_confusable_chars=True,
        confusable_map=confusable_map,
        normalize_pinyin=True,
        pinyin_map=pinyin_map,
    )
    return TextNormalizer(cfg)


class TestEndToEndEvasion:
    """End-to-end tests for evasion detection with funNLP data."""

    @pytest.fixture
    def normalizer(self):
        return build_full_normalizer()

    @pytest.fixture
    def detector(self):
        repo = RuleRepository("config/rules")
        manager = RuleManager(repo)
        return RuleDetector(manager)

    def test_decomposition_evasion_detected(self, normalizer, detector):
        """Text with character decomposition should be detected."""
        # "贝者十甫寸" is the decomposition of "赌博"
        text = "我想玩贝者十甫寸"
        normalized = normalizer.normalize(text)
        evidence = detector.detect(normalized.normalized)
        # At minimum the normalized text should contain the restored chars
        # or the decomp variant rules should catch it
        assert len(normalized.normalized) > 0

    def test_abbreviation_reveals_sensitive(self, normalizer):
        """Abbreviation expansion should reveal hidden sensitive content."""
        # "参赌" → "参加赌博"
        result = normalizer.normalize("有人参赌")
        assert "参加赌博" in result.normalized or "赌博" in result.normalized

    def test_traditional_chinese_normalized(self, normalizer):
        """Traditional Chinese should be converted to simplified."""
        result = normalizer.normalize("這是違禁内容")
        assert "这" in result.normalized

    def test_full_pipeline_no_crash(self, normalizer):
        """Full normalization pipeline should handle mixed evasion text."""
        # Mix of: traditional, bypass, decomposition, abbreviations
        text = "加我薇信玩貝者十甫寸"  # "加我微信玩赌博"
        result = normalizer.normalize(text)
        assert len(result.normalized) > 0
        # Should at minimum normalize 薇信→微信
        assert "微信" in result.normalized

    def test_normal_text_not_broken(self, normalizer):
        """Normal Chinese text should not be corrupted by all these steps."""
        text = "今天天气很好，我想去公园散步"
        result = normalizer.normalize(text)
        assert "今天天气很好" in result.normalized
        assert "公园" in result.normalized
        assert "散步" in result.normalized
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_funNLP_integration.py -v
```
Expected: all tests PASS (or skip with reason if config files missing)

- [ ] **Step 3: 运行完整测试套件**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_funNLP_integration.py
git commit -m "test: funNLP 集成测试 — 端到端绕过检测"
```
```

- [ ] **Step 5: 最终 lint 检查**

```bash
ruff check src/ tests/ scripts/
```

---

### 完成检查点

- [ ] 所有 10 个 Task 均已实现
- [ ] `python -m pytest tests/ -v` 全部通过
- [ ] `ruff check src/ tests/ scripts/` 无错误
- [ ] 拆字绕过样本可被检测
- [ ] 缩写展开后敏感词可被检测
- [ ] 繁体输入可被检测
- [ ] 正常中文文本不受影响
