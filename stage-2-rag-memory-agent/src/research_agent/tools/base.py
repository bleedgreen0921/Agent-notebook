"""工具公共接口与执行上下文。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from ..errors import ToolError
from ..models import ToolResponse


@dataclass(frozen=True, slots=True)
class ToolContext:
    workspace_root: Path
    cancel_event: Event
    deadline: float

    def raise_if_cancelled(self) -> None:
        if self.cancel_event.is_set() or time.monotonic() >= self.deadline:
            raise ToolError("工具执行已取消或超时")


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse: ...


@dataclass(frozen=True, slots=True)
class ToolExecution:
    tool_name: str
    fingerprint: str
    duration_ms: int
    response: ToolResponse
