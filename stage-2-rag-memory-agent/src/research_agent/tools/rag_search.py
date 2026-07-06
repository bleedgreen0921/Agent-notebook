"""把本地 RAG 检索包装为 Agent 工具。"""

from __future__ import annotations

from typing import Any

from ..models import ToolResponse
from ..rag.retriever import Retriever
from .base import ToolContext


class RAGSearchTool:
    name = "rag_search"
    description = "在已索引的本地资料中进行语义检索，并返回可引用的原文片段。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索问题或关键词"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        context.raise_if_cancelled()
        if not isinstance(arguments, dict) or not isinstance(arguments.get("query"), str):
            return ToolResponse.error("rag_search 需要字符串 query", "INVALID_ARGUMENTS")
        query = arguments["query"].strip()
        top_k = arguments.get("top_k", 5)
        if not query or not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 10:
            return ToolResponse.error("query 不能为空且 top_k 必须在 1-10", "INVALID_ARGUMENTS")
        hits = self._retriever.retrieve(query, top_k)
        if not hits:
            return ToolResponse.empty("本地知识库没有找到相关内容")
        data = [
            {
                "title": hit.title,
                "content": hit.content,
                "score": round(hit.score, 4),
                "locator": hit.locator,
            }
            for hit in hits
        ]
        return ToolResponse.success(
            f"找到 {len(hits)} 个本地资料片段",
            data=data,
            sources=self._retriever.to_sources(hits),
        )
