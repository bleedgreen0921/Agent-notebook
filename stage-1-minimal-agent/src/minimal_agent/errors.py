"""项目使用的错误类型。"""


class AppError(Exception):
    """所有可识别错误的基类，code 便于日志和上层程序分类处理。"""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class ConfigError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFIG_ERROR")


class LLMError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "LLM_ERROR")


class ProtocolError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "PROTOCOL_ERROR")


class ToolError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "TOOL_ERROR")


class AgentLimitError(AppError):
    def __init__(self, message: str, code: str) -> None:
        if code not in {"MAX_STEPS", "AGENT_TIMEOUT"}:
            raise ValueError(f"未知的 Agent 限制错误码：{code}")
        super().__init__(message, code)
