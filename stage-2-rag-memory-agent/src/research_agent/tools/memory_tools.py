"""让 Agent 显式读取和写入长期记忆。"""

from __future__ import annotations

from typing import Any

from ..memory.long_term import LongTermMemoryStore
from ..models import ToolResponse
from .base import ToolContext


class RecallMemoryTool:
    name = "recall_memory"
    description = "检索当前用户命名空间中的长期记忆；记忆不是外部事实来源。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, store: LongTermMemoryStore, namespace: str) -> None:
        self._store = store
        self._namespace = namespace

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        context.raise_if_cancelled()
        if not isinstance(arguments, dict) or not isinstance(arguments.get("query"), str):
            return ToolResponse.error("recall_memory 需要字符串 query", "INVALID_ARGUMENTS")
        records = self._store.recall(self._namespace, arguments["query"], top_k=5)
        if not records:
            return ToolResponse.empty("没有找到相关长期记忆")
        return ToolResponse.success(
            f"召回 {len(records)} 条长期记忆",
            data=[
                {"memory_id": item.memory_id, "content": item.content, "score": round(item.score, 4)}
                for item in records
            ],
        )


class SaveMemoryTool:
    name = "save_memory"
    description = "仅在用户明确要求记住稳定偏好或事实时写入长期记忆。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "reason": {"type": "string", "description": "说明用户为何要求保存"},
        },
        "required": ["content", "reason"],
        "additionalProperties": False,
    }

    def __init__(self, store: LongTermMemoryStore, namespace: str) -> None:
        self._store = store
        self._namespace = namespace

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        context.raise_if_cancelled()
        if not isinstance(arguments, dict):
            return ToolResponse.error("save_memory 参数必须是对象", "INVALID_ARGUMENTS")
        content = arguments.get("content")
        reason = arguments.get("reason")
        if (
            not isinstance(content, str)
            or not content.strip()
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            return ToolResponse.error("content 和 reason 必须是非空字符串", "INVALID_ARGUMENTS")
        memory_id = self._store.save(
            self._namespace,
            content,
            {"reason": reason.strip(), "source": "explicit_agent_tool"},
        )
        return ToolResponse.success("长期记忆已保存", data={"memory_id": memory_id})
