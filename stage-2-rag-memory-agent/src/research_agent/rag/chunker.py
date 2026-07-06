"""保留段落边界并带重叠窗口的文本分块器。"""

from __future__ import annotations

import re

from .models import TextChunk

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n+")


class TextChunker:
    def __init__(self, *, max_chars: int = 1_200, overlap_chars: int = 200) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars 必须大于 0")
        if not 0 <= overlap_chars < max_chars:
            raise ValueError("overlap_chars 必须在 0 和 max_chars 之间")
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def split(self, text: str) -> list[TextChunk]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        # 先按段落切分；超长段落再按字符窗口切分。
        units: list[str] = []
        for paragraph in _PARAGRAPH_BREAK.split(normalized):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) <= self._max_chars:
                units.append(paragraph)
            else:
                units.extend(self._split_long_unit(paragraph))

        chunks: list[TextChunk] = []
        current = ""
        approximate_start = 0
        for unit in units:
            candidate = f"{current}\n\n{unit}" if current else unit
            if len(candidate) <= self._max_chars:
                current = candidate
                continue
            if current:
                chunks.append(self._make_chunk(len(chunks), current, approximate_start))
                approximate_start += max(1, len(current) - self._overlap_chars)
                # unit 本身可能接近上限，只保留能够容纳的重叠前缀。
                available_prefix = max(0, self._max_chars - len(unit) - 2)
                prefix_size = min(self._overlap_chars, available_prefix)
                prefix = current[-prefix_size:] if prefix_size else ""
                current = f"{prefix}\n\n{unit}".strip()
            else:
                current = unit

        if current:
            chunks.append(self._make_chunk(len(chunks), current, approximate_start))
        return chunks

    def _split_long_unit(self, text: str) -> list[str]:
        step = self._max_chars - self._overlap_chars
        return [text[start : start + self._max_chars] for start in range(0, len(text), step)]

    @staticmethod
    def _make_chunk(index: int, content: str, start: int) -> TextChunk:
        end = start + len(content)
        return TextChunk(index, content, f"字符 {start}-{end}")
