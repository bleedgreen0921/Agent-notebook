"""工具系统使用的公共类型。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from ..errors import ToolError


@dataclass(frozen=True, slots=True)
class ToolContext:
    """提供文件访问边界、取消信号和单次工具截止时间。"""

    workspace_root: Path
    cancel_event: Event
    deadline: float

    def raise_if_cancelled(self) -> None:
        if self.cancel_event.is_set() or time.monotonic() >= self.deadline:
            raise ToolError("工具执行已取消或超时")


class Tool(Protocol):
    """所有工具必须遵守的接口。"""

    name: str
    description: str
    input_schema: dict[str, Any]

    def execute(self, arguments: object, context: ToolContext) -> object:
        """校验参数、执行工具并返回可被 JSON 序列化的数据。"""
        ...


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    ok: bool
    tool_name: str
    duration_ms: int
    output: object | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": self.ok,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
        }
        if self.ok:
            result["output"] = self.output
        else:
            result["error"] = self.error or "未知工具错误"
        return result
