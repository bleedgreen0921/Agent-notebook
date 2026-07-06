"""为工具来源分配稳定的 S1、S2 等局部引用编号。"""

from __future__ import annotations

from ..models import EvidenceSource, RegisteredSource


class EvidenceLedger:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str | None], RegisteredSource] = {}
        self._by_id: dict[str, RegisteredSource] = {}

    def register(self, sources: tuple[EvidenceSource, ...]) -> list[RegisteredSource]:
        registered: list[RegisteredSource] = []
        for source in sources:
            key = (source.uri, source.locator)
            existing = self._by_key.get(key)
            if existing is None:
                source_id = f"S{len(self._by_id) + 1}"
                existing = RegisteredSource(
                    source_id, source.title, source.uri, source.snippet, source.locator
                )
                self._by_key[key] = existing
                self._by_id[source_id] = existing
            elif len(source.snippet) > len(existing.snippet):
                # 同一页面后续抓取到更完整正文时更新证据，但保留原编号。
                existing = RegisteredSource(
                    existing.source_id,
                    source.title or existing.title,
                    source.uri,
                    source.snippet,
                    source.locator,
                )
                self._by_key[key] = existing
                self._by_id[existing.source_id] = existing
            registered.append(existing)
        return registered

    def get(self, source_id: str) -> RegisteredSource | None:
        return self._by_id.get(source_id)

    def all(self) -> tuple[RegisteredSource, ...]:
        return tuple(self._by_id.values())
