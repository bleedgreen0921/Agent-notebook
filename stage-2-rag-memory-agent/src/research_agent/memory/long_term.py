"""按 namespace 隔离、使用 embedding 召回的长期记忆。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from ..rag.embeddings import EmbeddingProvider
from ..storage.database import Database


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    content: str
    metadata: dict[str, object]
    score: float


class LongTermMemoryStore:
    def __init__(self, database: Database, embeddings: EmbeddingProvider) -> None:
        self._database = database
        self._embeddings = embeddings

    def save(
        self,
        namespace: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        normalized = content.strip()
        if not namespace.strip() or not normalized:
            raise ValueError("namespace 和 content 不能为空")
        memory_id = hashlib.sha256(
            f"{namespace}\n{normalized}".encode("utf-8")
        ).hexdigest()[:24]
        vector = self._embeddings.embed([normalized])[0]
        with self._database.transaction() as connection:
            connection.execute(
                """INSERT INTO long_term_memories
                   (memory_id, namespace, content, metadata_json, embedding_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(memory_id) DO UPDATE SET
                       metadata_json = excluded.metadata_json,
                       embedding_json = excluded.embedding_json""",
                (
                    memory_id,
                    namespace,
                    normalized,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(vector),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return memory_id

    def recall(
        self,
        namespace: str,
        query: str,
        *,
        top_k: int = 5,
        min_score: float = 0.05,
    ) -> list[MemoryRecord]:
        if not query.strip():
            return []
        query_vector = self._embeddings.embed([query])[0]
        with self._database.connection() as connection:
            rows = connection.execute(
                """SELECT memory_id, content, metadata_json, embedding_json
                   FROM long_term_memories WHERE namespace = ?""",
                (namespace,),
            ).fetchall()
        records: list[MemoryRecord] = []
        for row in rows:
            try:
                vector = [float(value) for value in json.loads(row["embedding_json"])]
                metadata = json.loads(row["metadata_json"])
                if not isinstance(metadata, dict):
                    metadata = {}
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            score = _cosine(query_vector, vector)
            if score >= min_score:
                records.append(
                    MemoryRecord(str(row["memory_id"]), str(row["content"]), metadata, score)
                )
        records.sort(key=lambda record: record.score, reverse=True)
        return records[:top_k]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norms = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
    return 0.0 if norms == 0 else dot / norms
