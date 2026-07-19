"""无外部依赖的 Aho-Corasick 自动机，用于关键词字面量规则匹配。

支持在单次文本扫描中同时匹配大量关键词，时间复杂度 O(n+m)，
其中 n 为文本长度，m 为匹配到的模式总数。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class _Node:
    """一个 trie 节点，包含子节点、失败链接和终止规则序号。"""

    children: dict[str, int] = field(default_factory=dict)
    failure: int = 0
    outputs: list[int] = field(default_factory=list)


class KeywordAutomaton:
    """在单次文本扫描中匹配大量小写 Unicode 关键词模式。

    基于经典的 Aho-Corasick 算法实现，包含 trie 构建和失败链接 BFS。
    """

    def __init__(self, patterns: Iterable[tuple[str, int]]):
        self._nodes = [_Node()]
        for pattern, ordinal in patterns:
            self._insert(pattern, ordinal)
        self._build_failure_links()

    def search(self, text: str) -> set[int]:
        """在文本中搜索，返回至少命中一次的所有规则序号。

        Args:
            text: 待搜索的小写文本。

        Returns:
            命中规则的序号集合（每个规则最多出现一次）。
        """
        state = 0
        matched: set[int] = set()
        for character in text:
            while state and character not in self._nodes[state].children:
                state = self._nodes[state].failure
            state = self._nodes[state].children.get(character, 0)
            matched.update(self._nodes[state].outputs)
        return matched

    def _insert(self, pattern: str, ordinal: int) -> None:
        """插入一个非空模式，保留终止节点的规则序号。"""
        state = 0
        for character in pattern:
            next_state = self._nodes[state].children.get(character)
            if next_state is None:
                next_state = len(self._nodes)
                self._nodes[state].children[character] = next_state
                self._nodes.append(_Node())
            state = next_state
        self._nodes[state].outputs.append(ordinal)

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
                self._nodes[child].failure = self._nodes[failure].children.get(character, 0)
                # 输出合并：子节点继承失败链接目标的输出
                self._nodes[child].outputs.extend(self._nodes[self._nodes[child].failure].outputs)
