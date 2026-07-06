"""模型结构化输出协议及运行时解析。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from ..errors import ProtocolError

_JSON_CODE_FENCE = re.compile(
    r"^```(?:json)?\s*([\s\S]*?)\s*```$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FinalDecision:
    type: Literal["final"]
    answer: str


@dataclass(frozen=True, slots=True)
class ToolCallDecision:
    type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, object]


AgentDecision = FinalDecision | ToolCallDecision


def parse_agent_decision(raw_content: str) -> AgentDecision:
    """
    解析并逐字段校验模型输出。

    Python 类型标注不会在运行时自动检查外部 JSON，因此这些判断不能省略。
    """

    normalized = _strip_markdown_code_fence(raw_content.strip())
    try:
        value: Any = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ProtocolError("模型输出不是合法 JSON") from error

    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ProtocolError("模型输出必须是包含 type 字段的 JSON 对象")

    decision_type = value["type"]
    if decision_type == "final":
        answer = value.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ProtocolError("final 输出必须包含非空字符串 answer")
        return FinalDecision(type="final", answer=answer.strip())

    if decision_type == "tool_call":
        tool_name = value.get("tool_name")
        arguments = value.get("arguments")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ProtocolError("tool_call 输出必须包含非空字符串 tool_name")
        if not isinstance(arguments, dict):
            raise ProtocolError("tool_call 输出必须包含对象类型 arguments")
        return ToolCallDecision(
            type="tool_call",
            tool_name=tool_name.strip(),
            arguments=arguments,
        )

    raise ProtocolError(f"不支持的决策类型：{decision_type}")


def _strip_markdown_code_fence(content: str) -> str:
    """允许完整 JSON 外的一层代码围栏，但不提取混杂自然语言。"""

    match = _JSON_CODE_FENCE.fullmatch(content)
    return match.group(1) if match else content
