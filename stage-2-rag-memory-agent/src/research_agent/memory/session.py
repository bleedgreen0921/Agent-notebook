"""跨多次 CLI 调用保存同一会话的用户问题和最终回答。"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import ChatMessage
from ..storage.database import Database


class SessionMemoryStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def append(self, session_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("会话记忆只保存 user 或 assistant 消息")
        with self._database.transaction() as connection:
            connection.execute(
                """INSERT INTO session_messages(session_id, role, content, created_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, role, content, datetime.now(timezone.utc).isoformat()),
            )

    def load_recent(self, session_id: str, limit: int = 12) -> list[ChatMessage]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """SELECT role, content FROM session_messages
                   WHERE session_id = ? ORDER BY message_id DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        messages: list[ChatMessage] = []
        for row in reversed(rows):
            role = str(row["role"])
            content = str(row["content"])
            if role == "user":
                messages.append(ChatMessage("user", content))
            elif role == "assistant":
                messages.append(ChatMessage("assistant", content))
        return messages
