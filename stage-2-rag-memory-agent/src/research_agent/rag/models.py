"""RAG 管线内部数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDocument:
    document_id: str
    title: str
    source_uri: str
    content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_index: int
    content: str
    locator: str


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    title: str
    source_uri: str
    content: str
    locator: str | None
    score: float
