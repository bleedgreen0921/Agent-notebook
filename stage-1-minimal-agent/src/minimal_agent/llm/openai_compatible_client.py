"""OpenAI-compatible Chat Completions HTTP 客户端。"""

from __future__ import annotations

import json
import socket
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..errors import LLMError
from ..models import ChatMessage

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class OpenAICompatibleClient:
    """
    使用 Python 标准库调用 OpenAI-compatible API。

    不使用厂商 SDK，目的是让 Stage 1 的请求、响应与错误处理保持可见。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        default_timeout_ms: int,
    ) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms 必须大于 0")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._default_timeout_ms = default_timeout_ms

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        timeout_ms: int | None = None,
    ) -> str:
        actual_timeout_ms = (
            self._default_timeout_ms if timeout_ms is None else timeout_ms
        )
        if actual_timeout_ms <= 0:
            raise LLMError("LLM 请求超时必须大于 0ms")

        body = json.dumps(
            {
                "model": self._model,
                "messages": [message.to_dict() for message in messages],
                "temperature": temperature,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self._base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )

        try:
            # urllib 的 timeout 单位是秒，项目配置统一使用毫秒。
            with urlopen(request, timeout=actual_timeout_ms / 1_000) as response:
                response_bytes = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            # 截断上游错误正文，避免把巨大 HTML 页面塞进异常信息。
            error_body = error.read(1_001).decode("utf-8", errors="replace")
            raise LLMError(
                f"LLM API 请求失败（HTTP {error.code}）：{error_body[:1_000]}"
            ) from error
        except (TimeoutError, socket.timeout) as error:
            raise LLMError(f"LLM API 请求超过 {actual_timeout_ms}ms") from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise LLMError(
                    f"LLM API 请求超过 {actual_timeout_ms}ms"
                ) from error
            raise LLMError(f"LLM API 网络异常：{error.reason}") from error
        except OSError as error:
            raise LLMError(f"LLM API 请求异常：{error}") from error

        if len(response_bytes) > _MAX_RESPONSE_BYTES:
            raise LLMError(f"LLM API 响应超过 {_MAX_RESPONSE_BYTES} 字节限制")

        try:
            payload: Any = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMError("LLM API 返回的不是合法 UTF-8 JSON") from error

        content = _extract_assistant_content(payload)
        if not content.strip():
            raise LLMError("LLM API 返回了空内容")
        return content


def _extract_assistant_content(payload: Any) -> str:
    """逐层校验外部响应，同时兼容字符串和 text-part 数组。"""

    if not isinstance(payload, dict):
        raise LLMError("LLM API 响应必须是 JSON 对象")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError("LLM API 响应缺少非空 choices 数组")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMError("LLM API 响应中的 choices[0] 不是对象")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMError("LLM API 响应缺少 choices[0].message")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        return "".join(text_parts)

    raise LLMError("LLM API 响应中的 message.content 格式不受支持")
