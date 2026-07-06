"""研究 Agent 的结构化模型决策协议。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from ..errors import ProtocolError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ToolCallDecision:
    type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class FinalDecision:
    type: Literal["final"]
    answer: str
    citations: list[str]


AgentDecision = ToolCallDecision | FinalDecision


def parse_decision(raw: str) -> AgentDecision:
    normalized = raw.strip()
    fence = _CODE_FENCE.fullmatch(normalized)
    if fence:
        normalized = fence.group(1)
    try:
        value: Any = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ProtocolError("模型输出不是合法 JSON") from error
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ProtocolError("模型输出必须是包含 type 的 JSON 对象")

    if value["type"] == "tool_call":
        name = value.get("tool_name")
        arguments = value.get("arguments")
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            raise ProtocolError("tool_call 需要非空 tool_name 和对象 arguments")
        return ToolCallDecision("tool_call", name.strip(), arguments)

    if value["type"] == "final":
        answer = value.get("answer")
        citations = value.get("citations")
        if not isinstance(answer, str) or not answer.strip():
            raise ProtocolError("final 需要非空字符串 answer")
        if not isinstance(citations, list) or not all(
            isinstance(item, str) for item in citations
        ):
            raise ProtocolError("final 需要字符串数组 citations")
        return FinalDecision("final", answer.strip(), citations)

    raise ProtocolError(f"不支持的决策类型：{value['type']}")
