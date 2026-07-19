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

import re
from dataclasses import dataclass, field


# ---- CJK character detection ----

# Common CJK Unicode ranges
_CJK_RANGES = [
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs (常用汉字)
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
]


def _is_cjk(ch: str) -> bool:
    """判断字符是否为 CJK（中日韩）表意文字。"""
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _contains_cjk(s: str) -> bool:
    """判断字符串是否包含至少一个 CJK 字符。"""
    return any(_is_cjk(ch) for ch in s)


def _replace_ascii_boundary(text: str, variant: str, replacement: str) -> str:
    """仅在 token 边界处将 `variant` 替换为 `replacement`。

    token 边界包括：字符串开头/结尾、空白、标点、CJK 字符或符号
    ——即任何非字母数字的位置。这可以防止 "bc" 匹配到 "abc123" 内部。
    """
    if variant not in text:
        return text
    # Build a regex that matches `variant` only when surrounded by
    # non-alphanumeric characters (or string boundaries).
    # Use lookbehind/lookahead to ensure we don't consume the boundaries.
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(variant) + r"(?![a-zA-Z0-9])"
    return re.sub(pattern, replacement, text)


# ---- Separator characters commonly used for keyword evasion ----

# Characters that are inserted between CJK characters to evade keyword matching.
# Includes ASCII punctuation and Chinese punctuation marks.
_EVASION_SEPARATORS = frozenset("/|\\-_*.,·•～~!#^&+=;；，、。，．")


@dataclass
class NormalizerConfig:
    """TextNormalizer 的配置类。"""

    lowercase: bool = True
    full_to_half: bool = True
    normalize_whitespace: bool = True
    reduce_repeated_chars: bool = True
    max_repeat: int = 3
    normalize_symbols: bool = True
    normalize_bypass: bool = True
    bypass_map: dict[str, str] = field(default_factory=dict)
    # New: strip evasion separators between isolated single CJK chars
    strip_evasion_separators: bool = True
    # New: normalize confusable characters (形近字/同音字)
    normalize_confusable_chars: bool = True
    confusable_map: dict[str, str] = field(default_factory=dict)
    # New: pinyin-aware normalization (requires pypinyin for dynamic mode)
    normalize_pinyin: bool = True
    pinyin_map: dict[str, str] = field(default_factory=dict)
    # New: traditional Chinese -> simplified Chinese
    normalize_traditional: bool = True
    traditional_simplified_map: dict[str, str] = field(default_factory=dict)
    # New: abbreviation expansion
    normalize_abbreviations: bool = True
    abbreviation_map: dict[str, str] = field(default_factory=dict)
    # New: character decomposition restoration (Path B)
    normalize_decomposition: bool = True
    decomposition_map: dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizedText:
    """文本规范化的结果。"""

    original: str
    normalized: str
    # Position mapping: normalized index → original index (approximate)
    position_map: list[int] = field(default_factory=list)


class TextNormalizer:
    """在检测前对文本进行预处理，消除各种绕过手段。

    处理：全角/半角转换、大小写归一化、空白归一化、绕过变体归一化
    （谐音、形近、拼音等）、重复字符压缩、绕过分隔符剥离、
    混淆字归一化、符号归一化。
    """

    def __init__(self, config: NormalizerConfig | None = None):
        self.config = config or NormalizerConfig()

    def normalize(self, text: str) -> NormalizedText:
        """执行所有已启用的规范化步骤。"""
        result = text
        for step in [
            self._normalize_full_to_half,
            self._normalize_traditional_chinese,
            self._normalize_abbreviations,
            self._normalize_decomposition,
            self._normalize_bypass_variants,
            self._normalize_confusable_chars,
            self._normalize_pinyin_variants,
            self._normalize_case,
            self._strip_evasion_separators,
            self._normalize_whitespace,
            self._reduce_repeats,
            self._normalize_symbols,
        ]:
            if self._is_enabled(step.__name__):
                result = step(result)
        return NormalizedText(original=text, normalized=result)

    def _is_enabled(self, step_name: str) -> bool:
        """检查某个规范化步骤是否在配置中启用。"""
        mapping = {
            "_normalize_full_to_half": self.config.full_to_half,
            "_normalize_case": self.config.lowercase,
            "_normalize_whitespace": self.config.normalize_whitespace,
            "_normalize_bypass_variants": self.config.normalize_bypass,
            "_reduce_repeats": self.config.reduce_repeated_chars,
            "_normalize_symbols": self.config.normalize_symbols,
            "_strip_evasion_separators": self.config.strip_evasion_separators,
            "_normalize_confusable_chars": self.config.normalize_confusable_chars,
            "_normalize_pinyin_variants": self.config.normalize_pinyin,
            "_normalize_traditional_chinese": self.config.normalize_traditional,
            "_normalize_abbreviations": self.config.normalize_abbreviations,
            "_normalize_decomposition": self.config.normalize_decomposition,
        }
        return mapping.get(step_name, True)

    # ---- Individual normalization steps ----

    def _normalize_full_to_half(self, text: str) -> str:
        """将全角字符转换为半角。

        全角范围：FF01-FF5E → 半角 21-7E（偏移量：FEE0）
        全角空格：3000 → 20
        """
        result = []
        for ch in text:
            code = ord(ch)
            if code == 0x3000:
                result.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(ch)
        return "".join(result)

    def _normalize_case(self, text: str) -> str:
        """转换为小写。"""
        return text.lower()

    def _normalize_whitespace(self, text: str) -> str:
        """将多个空白字符折叠为单个空格。"""
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_bypass_variants(self, text: str) -> str:
        """将已知绕过变体替换为其标准形式。

        处理：谐音（薇信→微信）、形近（草你→操你）、
        拼音（weixin→微信）、符号变体（+V→加微信）、数字暗号（419→一夜情）。

        ASCII 条目使用词边界匹配防止假阳性（如 "bc" 匹配到 "abc123" 内部）；
        CJK 条目使用纯子串匹配（多字 CJK 短语安全）。
        """
        if not self.config.bypass_map:
            return text
        str_map = {str(k): str(v) for k, v in self.config.bypass_map.items()}
        # 按长度降序遍历，优先匹配最长变体，防止短变体抢先匹配
        for variant in sorted(str_map, key=len, reverse=True):
            replacement = str_map[variant]
            if _contains_cjk(variant):
                # CJK 变体：可直接使用子串匹配（多字 CJK 短语不会误伤）
                if variant in text:
                    text = text.replace(variant, replacement)
            else:
                # ASCII 变体：按长度选择匹配策略
                if len(variant) <= 3:
                    # 短 ASCII 键（如 vx、wx）：使用纯子串匹配，
                    # 使其能命中相邻数字的情况（如 "vx123"），
                    # 词边界匹配会遗漏此类情况。
                    if variant in text:
                        text = text.replace(variant, replacement)
                else:
                    # 较长 ASCII 变体：使用词边界匹配，
                    # 避免匹配到较长字母数字 token 的子串
                    # （如 "bc" 匹配到 "abc123"）。
                    text = _replace_ascii_boundary(text, variant, replacement)
        return text

    def _normalize_pinyin_variants(self, text: str) -> str:
        """替换拼音匹配到已知敏感词的 CJK 片段，同时替换文本中的原始 ASCII 拼音。

        使用 pypinyin 进行动态 CJK→拼音转换（如果可用）。
        始终对拼音字面量（如 "zhadan"）执行 ASCII 回退替换。
        """
        if not self.config.pinyin_map:
            return text

        str_map = {str(k): str(v) for k, v in self.config.pinyin_map.items()}

        # Always replace raw ASCII pinyin variants (e.g. "zhadan" → "炸弹")
        for variant in sorted(str_map, key=len, reverse=True):
            if variant in text:
                text = text.replace(variant, str_map[variant])

        # Try dynamic CJK→pinyin conversion for disguised characters
        try:
            import pypinyin

            return self._pinyin_cjk_replace(text, str_map, pypinyin)
        except ImportError:
            pass

        return text

    @staticmethod
    def _pinyin_cjk_replace(text: str, str_map: dict[str, str], pypinyin) -> str:
        """使用 pypinyin 将 CJK 片段转换为拼音后进行匹配替换。

        采用滑动窗口策略：遍历 CJK 字符的连续序列，对各长度的子串
        分别计算拼音并检查是否命中映射表中的敏感词拼音。
        """
        # 获取整段文本的拼音列表
        # pypinyin.lazy_pinyin 返回一维列表，如 ['wo', 'ai', 'ni']
        pinyin_list = pypinyin.lazy_pinyin(text, style=pypinyin.Style.TONE3, errors="ignore")
        n = len(text)
        result = list(text)

        # 建立文本位置到拼音列表索引的映射（非 CJK 字符对应 None）
        pos_to_pinyin: list[int | None] = [None] * n
        pi = 0
        for ti, ch in enumerate(text):
            if _is_cjk(ch) and pi < len(pinyin_list):
                pos_to_pinyin[ti] = pi
                pi += 1

        # 提取所有 CJK 字符的位置
        cjk_positions = [ti for ti, pi_val in enumerate(pos_to_pinyin) if pi_val is not None]

        # 滑动窗口：尝试不同长度的 CJK 连续子串，检查其拼音是否命中映射
        for start in range(len(cjk_positions)):
            # 限制最长窗口为 8 个字符，防止极端性能问题
            for end in range(start + 1, min(start + 8, len(cjk_positions) + 1)):
                span_start = cjk_positions[start]
                span_end = cjk_positions[end - 1] + 1
                cjk_span = text[span_start:span_end]
                # 获取该子串中各 CJK 字符的拼音索引
                pinyin_indices = [
                    pos_to_pinyin[i]
                    for i in range(span_start, span_end)
                    if pos_to_pinyin[i] is not None
                ]
                if not pinyin_indices:
                    continue
                # 拼接拼音字符串
                pinyin_str = "".join(pinyin_list[idx] for idx in pinyin_indices)
                # 去除声调数字后进行匹配
                pinyin_flat = "".join(c for c in pinyin_str if not c.isdigit())
                if pinyin_flat in str_map:
                    replacement = str_map[pinyin_flat]
                    # 用标准词替换 CJK 片段
                    result[span_start:span_end] = list(replacement)

        return "".join(result)

    def _normalize_traditional_chinese(self, text: str) -> str:
        """将繁体汉字转换为简体汉字。

        使用配置中的 traditional_simplified_map，从 traditional_simplified.yaml 加载。
        """
        if not self.config.traditional_simplified_map:
            return text
        str_map = {str(k): str(v) for k, v in self.config.traditional_simplified_map.items()}
        result = []
        for ch in text:
            result.append(str_map.get(ch, ch))
        return "".join(result)

    def _normalize_abbreviations(self, text: str) -> str:
        """将已知缩写展开为完整形式。

        使用最长优先匹配防止部分匹配：
        "禁毒办" 应优先匹配 "禁毒办" 而非 "禁毒"。

        仅匹配中文缩写（2 个以上 CJK 字符），避免英文缩写的误匹配。
        """
        if not self.config.abbreviation_map:
            return text
        str_map = {str(k): str(v) for k, v in self.config.abbreviation_map.items()}

        # 第一阶段：将所有匹配项替换为唯一占位符标记。
        # 防止较短键在较长键的替换文本中被再次匹配
        # （如 "禁毒" 在 "禁毒办公室" 的替换结果中被匹配）。
        markers: dict[str, str] = {}
        for i, abbr in enumerate(sorted(str_map, key=len, reverse=True)):
            if len(abbr) < 2:
                continue
            if not _contains_cjk(abbr):
                continue
            if abbr in text:
                marker = f"\x00ABBR_{i}\x00"
                markers[marker] = str_map[abbr]
                text = text.replace(abbr, marker)

        # 第二阶段：将占位符替换为实际的展开文本。
        for marker, expansion in markers.items():
            text = text.replace(marker, expansion)
        return text

    def _normalize_decomposition(self, text: str) -> str:
        """还原拆字表达的 CJK 字符（全局扫描 + 词典验证）。

        检测攻击者将汉字拆分为独立部首以绕过关键词匹配的模式。
        仅当拆分组合不是真实汉语词汇时（通过 jieba 内置词频词典验证）
        才执行还原。

        示例：
            "木仓" → 不是真实词语 → "枪"（还原）
            "女子" → 真实词语（woman）→ 保持原样
        """
        if not self.config.decomposition_map:
            return text

        str_map = {str(k): str(v) for k, v in self.config.decomposition_map.items()}

        # 构建已知中文词语集合，用于词典验证
        try:
            import jieba

            _known_words: frozenset[str] = frozenset(w for w in jieba.dt.FREQ if len(w) >= 2)
            _has_dict = True
        except (ImportError, AttributeError):
            _known_words = frozenset()
            _has_dict = False

        result = list(text)
        n = len(text)

        i = 0
        while i < n:
            if n - i < 2:  # 剩余文本太短，无法构成任何拆字组合
                break
            matched = False
            candidate_len = 1  # 默认前进长度（未匹配时）
            # 从最长窗口（5 字符）开始向下尝试
            for window in range(min(5, n - i), 1, -1):
                candidate = text[i : i + window]
                if candidate not in str_map:
                    continue
                original_char = str_map[candidate]

                if _has_dict and candidate in _known_words:
                    # 这是词典中的真实词语——不还原
                    # （如 "女子" = woman，不是 "好" 的拆字）。
                    # 跳过整个候选文本，避免将其尾部错认为拆字。
                    matched = False
                    candidate_len = len(candidate)
                elif not _has_dict and len(candidate) == 2:
                    # 无词典可用：2 字组合风险太大
                    # （大多数中文真实词语是 2 字）。
                    matched = False
                    candidate_len = len(candidate)
                else:
                    # 非已知词语——很可能是拆字——执行还原
                    result[i : i + window] = [original_char]
                    matched = True
                break
            i += window if matched else candidate_len

        return "".join(result)

    def _normalize_confusable_chars(self, text: str) -> str:
        """将易混淆的 CJK 字符替换为标准形式。

        处理：形近字（形→行）、同音字替换（草→操）等。
        使用配置中的 confusable_map，从 confusable_chars.yaml 加载。

        与 bypass_variants（短语级别）不同，此方法在字符级别操作
        ——替换全文中每个易混淆的单个字符。
        """
        if not self.config.confusable_map:
            return text
        # Sort by key char; since these are single chars, ordering by
        # the character itself is fine (no overlap concerns like with phrases)
        str_map = {str(k): str(v) for k, v in self.config.confusable_map.items()}
        result = []
        for ch in text:
            result.append(str_map.get(ch, ch))
        return "".join(result)

    def _strip_evasion_separators(self, text: str) -> str:
        """剥离插入在孤立 CJK 字符之间的绕过分隔符。

        攻击者在敏感关键词的字符之间插入 / | - 等分隔符以绕过子串匹配：
        违/禁/词 → 违禁词。

        仅当分隔符两侧的 CJK 字符都是"孤立的"时才移除——即每个 CJK 字符
        的"外侧"紧邻的是另一分隔符或文本边界，而非多字 CJK 词的一部分。

        这样可以保留正常用法中的分隔符：
            违/禁/词    → 违禁词      (绕过，已移除 ✓)
            你/好       → 你好        (绕过，已移除 ✓)
            是///消防员  → 是消防员    (链式含多字词 ✓)
            双肩包/单肩包 → 保留       (正常用法 ✓)
            http://a/b  → 保留        (非 CJK ✓)
            加微信/QQ    → 保留        (一侧非 CJK ✓)
        """
        chars = list(text)
        n = len(chars)
        # 标记需要移除的位置
        remove = [False] * n

        i = 0
        while i < n:
            if chars[i] in _EVASION_SEPARATORS:
                # 向左越过空格和其他分隔符，找到第一个有意义的字符
                left = i - 1
                while left >= 0 and (chars[left].isspace() or chars[left] in _EVASION_SEPARATORS):
                    left -= 1

                # 向右越过空格和其他分隔符，找到第一个有意义的字符
                right = i + 1
                while right < n and (chars[right].isspace() or chars[right] in _EVASION_SEPARATORS):
                    right += 1

                # 两侧都必须存在且为 CJK 字符
                if left >= 0 and right < n:
                    if _is_cjk(chars[left]) and _is_cjk(chars[right]):
                        # 检查孤立性：CJK 字符在其"外侧"不相邻其他 CJK 字符
                        # 即为"孤立"。要求至少有一侧是孤立的——这样既能捕获
                        # 是///消防员 这类链式结构（"是"孤立，即使"消"是多字词的一部分），
                        # 又能保留 双肩包/单肩包（"包"和"单"都不孤立）。
                        left_isolated = left == 0 or not _is_cjk(chars[left - 1])
                        right_isolated = right == n - 1 or not _is_cjk(chars[right + 1])

                        if left_isolated or right_isolated:
                            remove[i] = True
                            # 同时移除移除的分隔符与孤立 CJK 字符之间的空格
                            _mark_adjacent_spaces(chars, i, n, remove)

            i += 1

        return "".join(ch for i, ch in enumerate(chars) if not remove[i])

    def _reduce_repeats(self, text: str) -> str:
        """压缩连续重复字符。

        例如，max_repeat=3 时，"aaaaaa" → "aaa"
        """
        max_r = self.config.max_repeat
        return re.sub(r"(.)\1{" + str(max_r) + r",}", r"\1" * max_r, text)

    def _normalize_symbols(self, text: str) -> str:
        """将常见变体符号标准化为标准形式。

        处理：中文标点变体、常见 leetspeak、形近字符替换。
        """
        symbol_map = {
            # Chinese punctuation → English
            "‘": "'",
            "’": "'",  # 左/右单引号
            "“": '"',
            "”": '"',  # 左/右双引号
            "，": ",",  # 全角逗号
            "。": ".",  # 句号
            "；": ";",  # 全角分号
            # Common leetspeak
            "@": "a",
            "$": "s",
            "0": "o",
        }
        result = []
        for ch in text:
            result.append(symbol_map.get(ch, ch))
        return "".join(result)


def _mark_adjacent_spaces(chars: list[str], idx: int, n: int, remove: list[bool]) -> None:
    """标记紧邻已移除分隔符的空格以待清理。

    当从 "违 / 禁" 中移除 "/" 时，也需要移除空格，
    使得结果为 "违禁" 而非 "违  禁"。后续的空白规范化步骤
    会折叠剩余间隙，但在此处移除可使中间输出更整洁。
    """
    # Left side spaces
    j = idx - 1
    while j >= 0 and chars[j].isspace() and not remove[j]:
        # Only remove if this space is between the removed sep and an isolated CJK
        remove[j] = True
        j -= 1
    # Right side spaces
    j = idx + 1
    while j < n and chars[j].isspace() and not remove[j]:
        remove[j] = True
        j += 1
