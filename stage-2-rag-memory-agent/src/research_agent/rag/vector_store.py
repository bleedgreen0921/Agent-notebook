"""基于 SQLite 和余弦相似度的教学型向量存储。"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from ..storage.database import Database
from .models import RetrievalHit, TextChunk, TextDocument


class SQLiteVectorStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_content_hash(self, document_id: str) -> str | None:
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT content_hash FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return None if row is None else str(row["content_hash"])

    def replace_document(
        self,
        document: TextDocument,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致")
        now = datetime.now(timezone.utc).isoformat()
        with self._database.transaction() as connection:
            connection.execute("DELETE FROM documents WHERE document_id = ?", (document.document_id,))
            connection.execute(
                """INSERT INTO documents
                (document_id, source_uri, title, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    document.document_id,
                    document.source_uri,
                    document.title,
                    document.content_hash,
                    now,
                ),
            )
            connection.executemany(
                """INSERT INTO rag_chunks
                (chunk_id, document_id, chunk_index, content, embedding_json, locator)
                VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        f"{document.document_id}:{chunk.chunk_index}",
                        document.document_id,
                        chunk.chunk_index,
                        chunk.content,
                        json.dumps(embedding),
                        chunk.locator,
                    )
                    for chunk, embedding in zip(chunks, embeddings, strict=True)
                ],
            )

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        min_score: float,
    ) -> list[RetrievalHit]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """SELECT c.chunk_id, c.document_id, c.content, c.embedding_json,
                          c.locator, d.title, d.source_uri
                   FROM rag_chunks AS c
                   JOIN documents AS d ON d.document_id = c.document_id"""
            ).fetchall()

        hits: list[RetrievalHit] = []
        for row in rows:
            try:
                vector = [float(value) for value in json.loads(row["embedding_json"])]
            except (TypeError, ValueError, json.JSONDecodeError):
                # 单条损坏向量不应让整个检索不可用。
                continue
            score = _cosine_similarity(query_vector, vector)
            if score < min_score:
                continue
            hits.append(
                RetrievalHit(
                    chunk_id=str(row["chunk_id"]),
                    document_id=str(row["document_id"]),
                    title=str(row["title"]),
                    source_uri=str(row["source_uri"]),
                    content=str(row["content"]),
                    locator=None if row["locator"] is None else str(row["locator"]),
                    score=score,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
