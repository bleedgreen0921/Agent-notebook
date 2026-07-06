"""项目统一错误类型。"""


class AppError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class ConfigError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFIG_ERROR")


class LLMError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "LLM_ERROR")


class EmbeddingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "EMBEDDING_ERROR")


class ProtocolError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "PROTOCOL_ERROR")


class ToolError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "TOOL_ERROR")


class StorageError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "STORAGE_ERROR")


class CitationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "CITATION_ERROR")


class AgentLimitError(AppError):
    def __init__(self, message: str, code: str) -> None:
        if code not in {"MAX_STEPS", "AGENT_TIMEOUT"}:
            raise ValueError(f"未知 Agent 限制错误码：{code}")
        super().__init__(message, code)
