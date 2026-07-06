"""工具注册、发现和限时执行。"""

from __future__ import annotations

import copy
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Event

from ..errors import ToolError
from .base import Tool, ToolContext, ToolExecutionResult

_VALID_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class ToolRegistry:
    """集中管理工具，统一处理重名、超时、异常和执行耗时。"""

    def __init__(
        self,
        *,
        workspace_root: Path,
        default_timeout_ms: int,
        max_workers: int = 4,
    ) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms 必须大于 0")
        if max_workers <= 0:
            raise ValueError("max_workers 必须大于 0")
        self._workspace_root = workspace_root
        self._default_timeout_ms = default_timeout_ms
        self._tools: dict[str, Tool] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="agent-tool",
        )
        self._closed = False

    def register(self, tool: Tool) -> None:
        if self._closed:
            raise ToolError("工具注册表已经关闭")
        if not _VALID_TOOL_NAME.fullmatch(tool.name):
            raise ToolError(f"工具名不合法：{tool.name}")
        if tool.name in self._tools:
            raise ToolError(f"工具重复注册：{tool.name}")
        self._tools[tool.name] = tool

    def describe(self) -> list[dict[str, object]]:
        """只向模型公开描述信息，不公开 Python 执行函数。"""

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": copy.deepcopy(tool.input_schema),
            }
            for tool in self._tools.values()
        ]

    def execute(
        self,
        tool_name: str,
        arguments: object,
        timeout_ms: int | None = None,
    ) -> ToolExecutionResult:
        started_at = time.monotonic()
        if self._closed:
            return self._failure(tool_name, started_at, "工具注册表已经关闭")

        tool = self._tools.get(tool_name)
        if tool is None:
            return self._failure(tool_name, started_at, f"未知工具：{tool_name}")

        actual_timeout_ms = (
            self._default_timeout_ms if timeout_ms is None else timeout_ms
        )
        if actual_timeout_ms <= 0:
            return self._failure(tool_name, started_at, "工具超时必须大于 0ms")

        cancel_event = Event()
        context = ToolContext(
            workspace_root=self._workspace_root,
            cancel_event=cancel_event,
            deadline=time.monotonic() + actual_timeout_ms / 1_000,
        )
        future = self._executor.submit(tool.execute, arguments, context)

        try:
            output = future.result(timeout=actual_timeout_ms / 1_000)
            return ToolExecutionResult(
                ok=True,
                tool_name=tool_name,
                output=output,
                duration_ms=_elapsed_ms(started_at),
            )
        except FutureTimeoutError:
            # Python 线程不能被外部强制终止，因此同时设置协作式取消信号。
            cancel_event.set()
            future.cancel()
            return self._failure(
                tool_name,
                started_at,
                f"工具 {tool_name} 执行超过 {actual_timeout_ms}ms",
            )
        except Exception as error:
            return self._failure(tool_name, started_at, str(error))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._executor.shutdown(wait=False, cancel_futures=True)

    def __enter__(self) -> ToolRegistry:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    @staticmethod
    def _failure(
        tool_name: str,
        started_at: float,
        error: str,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            ok=False,
            tool_name=tool_name,
            error=error or "未知工具错误",
            duration_ms=_elapsed_ms(started_at),
        )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1_000))
