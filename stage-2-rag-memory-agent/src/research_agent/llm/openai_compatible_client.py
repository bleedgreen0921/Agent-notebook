"""仅依赖标准库的 OpenAI-compatible Chat Completions 客户端。"""

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
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
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
        actual_timeout_ms = self._default_timeout_ms if timeout_ms is None else timeout_ms
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
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=actual_timeout_ms / 1_000) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            detail = error.read(1_001).decode("utf-8", errors="replace")[:1_000]
            raise LLMError(f"LLM API 请求失败（HTTP {error.code}）：{detail}") from error
        except (TimeoutError, socket.timeout) as error:
            raise LLMError(f"LLM API 请求超过 {actual_timeout_ms}ms") from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise LLMError(f"LLM API 请求超过 {actual_timeout_ms}ms") from error
            raise LLMError(f"LLM API 网络异常：{error.reason}") from error
        except OSError as error:
            raise LLMError(f"LLM API 请求异常：{error}") from error

        if len(raw) > _MAX_RESPONSE_BYTES:
            raise LLMError("LLM API 响应超过 2 MiB 限制")
        try:
            payload: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMError("LLM API 返回的不是合法 UTF-8 JSON") from error
        return _extract_content(payload)


def _extract_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise LLMError("LLM API 响应必须是 JSON 对象")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError("LLM API 响应缺少非空 choices")
    first = choices[0]
    if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
        raise LLMError("LLM API 响应缺少 choices[0].message")
    content = first["message"].get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        joined = "".join(parts)
        if joined.strip():
            return joined
    raise LLMError("LLM API 返回了空内容或不支持的 content 格式")
