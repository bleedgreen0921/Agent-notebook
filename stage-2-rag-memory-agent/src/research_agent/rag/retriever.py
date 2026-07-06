"""把查询向量化并返回带来源信息的检索结果。"""

from __future__ import annotations

from ..models import EvidenceSource
from .embeddings import EmbeddingProvider
from .models import RetrievalHit
from .vector_store import SQLiteVectorStore


class Retriever:
    def __init__(
        self,
        *,
        embeddings: EmbeddingProvider,
        vector_store: SQLiteVectorStore,
        default_top_k: int = 5,
        min_score: float = 0.1,
    ) -> None:
        self._embeddings = embeddings
        self._store = vector_store
        self._top_k = default_top_k
        self._min_score = min_score

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        normalized = query.strip()
        if not normalized:
            return []
        vector = self._embeddings.embed([normalized])[0]
        return self._store.search(
            vector,
            top_k=top_k or self._top_k,
            min_score=self._min_score,
        )

    @staticmethod
    def to_sources(hits: list[RetrievalHit]) -> tuple[EvidenceSource, ...]:
        return tuple(
            EvidenceSource(
                title=hit.title,
                uri=hit.source_uri,
                snippet=hit.content,
                locator=hit.locator,
            )
            for hit in hits
        )
