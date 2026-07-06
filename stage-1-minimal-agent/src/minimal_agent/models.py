"""模块之间共享的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """一条 LLM 对话消息。"""

    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMClient(Protocol):
    """LLM 客户端协议，使 Agent 不依赖具体模型厂商。"""

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        timeout_ms: int | None = None,
    ) -> str:
        """根据消息列表生成一段非空助手文本。"""
        ...
