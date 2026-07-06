"""为 RAG、会话记忆和长期记忆提供统一 SQLite 数据库。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..errors import StorageError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    locator TEXT,
    UNIQUE(document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id);

CREATE TABLE IF NOT EXISTS session_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_messages_session
ON session_messages(session_id, message_id);

CREATE TABLE IF NOT EXISTS long_term_memories (
    memory_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_long_term_memories_namespace
ON long_term_memories(namespace);
"""


class Database:
    """每次操作创建独立连接，使线程池中的工具可以安全共享数据库路径。"""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.transaction() as connection:
                connection.executescript(_SCHEMA)
        except (OSError, sqlite3.Error) as error:
            raise StorageError(f"初始化数据库失败：{error}") from error

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        except sqlite3.Error as error:
            raise StorageError(f"SQLite 操作失败：{error}") from error
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
