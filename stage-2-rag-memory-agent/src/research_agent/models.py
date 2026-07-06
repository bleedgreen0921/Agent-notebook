"""跨模块共享的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMClient(Protocol):
    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        timeout_ms: int | None = None,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """工具产生的原始证据；source_id 由 EvidenceLedger 统一分配。"""

    title: str
    uri: str
    snippet: str
    locator: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "title": self.title,
            "uri": self.uri,
            "snippet": self.snippet,
        }
        if self.locator:
            result["locator"] = self.locator
        return result


@dataclass(frozen=True, slots=True)
class ToolResponse:
    status: Literal["success", "empty", "error"]
    summary: str
    data: object | None = None
    sources: tuple[EvidenceSource, ...] = field(default_factory=tuple)
    error_code: str | None = None

    @classmethod
    def success(
        cls,
        summary: str,
        *,
        data: object | None = None,
        sources: Sequence[EvidenceSource] = (),
    ) -> ToolResponse:
        return cls("success", summary, data, tuple(sources))

    @classmethod
    def empty(cls, summary: str) -> ToolResponse:
        return cls("empty", summary)

    @classmethod
    def error(cls, summary: str, code: str = "TOOL_ERROR") -> ToolResponse:
        return cls("error", summary, error_code=code)


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    source_id: str
    title: str
    uri: str
    snippet: str
    locator: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "source_id": self.source_id,
            "title": self.title,
            "uri": self.uri,
            "snippet": self.snippet,
        }
        if self.locator:
            result["locator"] = self.locator
        return result
