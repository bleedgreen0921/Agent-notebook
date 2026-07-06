"""不涉及工具调用的普通多轮对话。"""

from __future__ import annotations

from ..models import ChatMessage, LLMClient


class SimpleChatSession:
    """用于单独验证“调用 LLM 完成普通对话”这一小目标。"""

    def __init__(
        self,
        llm: LLMClient,
        system_prompt: str = "你是一个简洁、准确的中文助手。",
    ) -> None:
        self._llm = llm
        self._messages = [ChatMessage(role="system", content=system_prompt)]

    def send(self, user_input: str) -> str:
        normalized_input = user_input.strip()
        if not normalized_input:
            raise ValueError("用户输入不能为空")

        self._messages.append(ChatMessage(role="user", content=normalized_input))
        try:
            answer = self._llm.complete(self._messages, temperature=0.2)
        except Exception:
            # 请求失败时撤销本轮用户消息，避免重试后上下文出现重复问题。
            self._messages.pop()
            raise

        self._messages.append(ChatMessage(role="assistant", content=answer))
        return answer

    @property
    def history(self) -> tuple[ChatMessage, ...]:
        """返回不可变快照，防止调用方直接修改内部历史。"""

        return tuple(self._messages)
