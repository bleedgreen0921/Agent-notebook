"""工具注册表：统一名称校验、限时执行和异常归一化。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Event

from ..models import ToolResponse
from .base import Tool, ToolContext, ToolExecution

_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class ToolRegistry:
    def __init__(self, *, workspace_root: Path, default_timeout_ms: int) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms 必须大于 0")
        self._root = workspace_root.expanduser().resolve()
        self._timeout_ms = default_timeout_ms
        self._tools: dict[str, Tool] = {}
        self._executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="research-tool")
        self._closed = False

    def register(self, tool: Tool) -> None:
        if self._closed:
            raise RuntimeError("工具注册表已经关闭")
        if not _TOOL_NAME.fullmatch(tool.name):
            raise ValueError(f"非法工具名：{tool.name}")
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册：{tool.name}")
        self._tools[tool.name] = tool

    def describe(self) -> list[dict[str, object]]:
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
        *,
        timeout_ms: int | None = None,
    ) -> ToolExecution:
        started = time.monotonic()
        fingerprint = _fingerprint(tool_name, arguments)
        tool = self._tools.get(tool_name)
        if self._closed:
            return self._result(tool_name, fingerprint, started, ToolResponse.error("工具注册表已关闭"))
        if tool is None:
            return self._result(
                tool_name,
                fingerprint,
                started,
                ToolResponse.error(f"未知工具：{tool_name}", "UNKNOWN_TOOL"),
            )

        actual_timeout = self._timeout_ms if timeout_ms is None else timeout_ms
        if actual_timeout <= 0:
            return self._result(
                tool_name, fingerprint, started, ToolResponse.error("工具超时必须大于 0ms")
            )
        cancel_event = Event()
        context = ToolContext(
            workspace_root=self._root,
            cancel_event=cancel_event,
            deadline=time.monotonic() + actual_timeout / 1_000,
        )
        future = self._executor.submit(tool.execute, arguments, context)
        try:
            response = future.result(timeout=actual_timeout / 1_000)
            if not isinstance(response, ToolResponse):
                response = ToolResponse.error("工具返回类型不正确", "INVALID_TOOL_RESPONSE")
        except FutureTimeoutError:
            cancel_event.set()
            future.cancel()
            response = ToolResponse.error(
                f"工具 {tool_name} 执行超过 {actual_timeout}ms", "TOOL_TIMEOUT"
            )
        except Exception as error:
            response = ToolResponse.error(str(error) or "未知工具异常", "TOOL_EXCEPTION")
        return self._result(tool_name, fingerprint, started, response)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._executor.shutdown(wait=False, cancel_futures=True)

    def __enter__(self) -> ToolRegistry:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    @staticmethod
    def _result(
        tool_name: str,
        fingerprint: str,
        started: float,
        response: ToolResponse,
    ) -> ToolExecution:
        return ToolExecution(
            tool_name=tool_name,
            fingerprint=fingerprint,
            duration_ms=max(0, round((time.monotonic() - started) * 1_000)),
            response=response,
        )


def _fingerprint(tool_name: str, arguments: object) -> str:
    try:
        canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        canonical = repr(arguments)
    return hashlib.sha256(f"{tool_name}\n{canonical}".encode("utf-8")).hexdigest()
