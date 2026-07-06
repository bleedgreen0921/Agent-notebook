"""仅存在于当前运行过程中的上下文窗口管理。"""

from __future__ import annotations

from ..models import ChatMessage

_NOTICE_RESERVE_CHARS = 120


class ShortTermMemory:
    """保留系统提示和最近消息，超预算时只在发送给 LLM 的快照中裁剪。"""

    def __init__(self, system_prompt: str, max_chars: int) -> None:
        if max_chars <= len(system_prompt) + _NOTICE_RESERVE_CHARS:
            raise ValueError("max_chars 必须大于系统提示词及裁剪通知长度")
        self._max_chars = max_chars
        self._messages = [ChatMessage("system", system_prompt)]
        self._pinned_indices: set[int] = set()

    def add(self, message: ChatMessage, *, pinned: bool = False) -> None:
        if message.role == "system":
            raise ValueError("ShortTermMemory 只允许一个系统消息")
        if pinned and len(message.content) >= (
            self._max_chars
            - len(self._messages[0].content)
            - _NOTICE_RESERVE_CHARS
        ):
            raise ValueError("固定消息超过短期上下文预算")
        self._messages.append(message)
        if pinned:
            self._pinned_indices.add(len(self._messages) - 1)

    def snapshot(self) -> tuple[ChatMessage, ...]:
        system = self._messages[0]
        # 预留裁剪通知空间，确保快照仍然不超过配置预算。
        remaining = self._max_chars - len(system.content) - _NOTICE_RESERVE_CHARS
        selected_indices = set(self._pinned_indices)
        for index in self._pinned_indices:
            remaining -= len(self._messages[index].content)
        for index in range(len(self._messages) - 1, 0, -1):
            if index in selected_indices:
                continue
            message = self._messages[index]
            cost = len(message.content)
            if cost > remaining:
                # 从最新消息向前选择；一旦放不下就不再回填更旧消息。
                break
            selected_indices.add(index)
            remaining -= cost
        selected = [self._messages[index] for index in sorted(selected_indices)]
        dropped = len(self._messages) - 1 - len(selected_indices)
        if dropped:
            notice = ChatMessage(
                "user",
                f"[短期上下文已裁剪：省略较早的 {dropped} 条消息；请以当前证据为准。]",
            )
            return (system, notice, *selected)
        return (system, *selected)

    @property
    def full_history(self) -> tuple[ChatMessage, ...]:
        return tuple(self._messages)
