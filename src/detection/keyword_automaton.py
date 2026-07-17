"""Dependency-free Aho-Corasick matcher for literal keyword rules."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class _Node:
    """One trie node with failure links and terminal rule ordinals."""

    children: dict[str, int] = field(default_factory=dict)
    failure: int = 0
    outputs: list[int] = field(default_factory=list)


class KeywordAutomaton:
    """Match many lowercase Unicode keyword patterns in one text scan."""

    def __init__(self, patterns: Iterable[tuple[str, int]]):
        self._nodes = [_Node()]
        for pattern, ordinal in patterns:
            self._insert(pattern, ordinal)
        self._build_failure_links()

    def search(self, text: str) -> set[int]:
        """Return all terminal rule ordinals matched at least once in text."""
        state = 0
        matched: set[int] = set()
        for character in text:
            while state and character not in self._nodes[state].children:
                state = self._nodes[state].failure
            state = self._nodes[state].children.get(character, 0)
            matched.update(self._nodes[state].outputs)
        return matched

    def _insert(self, pattern: str, ordinal: int) -> None:
        """Insert one non-empty pattern and preserve every terminal payload."""
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
        """Build breadth-first failure links after all patterns are inserted."""
        queue: deque[int] = deque()
        for child in self._nodes[0].children.values():
            queue.append(child)

        while queue:
            state = queue.popleft()
            for character, child in self._nodes[state].children.items():
                queue.append(child)
                failure = self._nodes[state].failure
                while failure and character not in self._nodes[failure].children:
                    failure = self._nodes[failure].failure
                self._nodes[child].failure = self._nodes[failure].children.get(character, 0)
                self._nodes[child].outputs.extend(self._nodes[self._nodes[child].failure].outputs)
