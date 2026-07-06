"""环境变量配置读取与校验。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigError


@dataclass(frozen=True, slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_ms: int


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    provider: str
    model: str
    dimensions: int


@dataclass(frozen=True, slots=True)
class AgentConfig:
    max_steps: int
    timeout_ms: int
    tool_timeout_ms: int
    context_max_chars: int
    retrieval_top_k: int
    retrieval_min_score: float


@dataclass(frozen=True, slots=True)
class AppConfig:
    llm: LLMConfig
    embedding: EmbeddingConfig
    agent: AgentConfig
    data_dir: Path
    workspace_root: Path
    search_api_url: str
    enable_code_execution: bool


def load_config(*, require_llm: bool = True) -> AppConfig:
    base_url = _read("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    _validate_url("LLM_BASE_URL", base_url)
    api_key = _read("LLM_API_KEY", "")
    model = _read("LLM_MODEL", "")
    if require_llm and (not api_key or not model):
        raise ConfigError("ask 命令需要 LLM_API_KEY 和 LLM_MODEL")

    provider = _read("EMBEDDING_PROVIDER", "local").lower()
    if provider not in {"local", "openai"}:
        raise ConfigError("EMBEDDING_PROVIDER 只能是 local 或 openai")
    if provider == "openai" and not api_key:
        raise ConfigError("openai embedding 需要 LLM_API_KEY")

    search_api_url = _read(
        "SEARCH_API_URL", "https://zh.wikipedia.org/w/api.php"
    )
    _validate_url("SEARCH_API_URL", search_api_url)
    data_dir = Path(_read("AGENT_DATA_DIR", ".agent-data")).expanduser()
    workspace_root = Path(_read("AGENT_WORKSPACE_ROOT", ".")).expanduser()

    return AppConfig(
        llm=LLMConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_ms=_read_positive_int("LLM_TIMEOUT_MS", 30_000),
        ),
        embedding=EmbeddingConfig(
            provider=provider,
            model=_read("EMBEDDING_MODEL", "text-embedding-3-small"),
            dimensions=_read_positive_int("EMBEDDING_DIMENSIONS", 256),
        ),
        agent=AgentConfig(
            max_steps=_read_positive_int("AGENT_MAX_STEPS", 12),
            timeout_ms=_read_positive_int("AGENT_TIMEOUT_MS", 180_000),
            tool_timeout_ms=_read_positive_int("TOOL_TIMEOUT_MS", 15_000),
            context_max_chars=_read_positive_int("CONTEXT_MAX_CHARS", 60_000),
            retrieval_top_k=_read_positive_int("RETRIEVAL_TOP_K", 5),
            retrieval_min_score=_read_float("RETRIEVAL_MIN_SCORE", 0.10),
        ),
        data_dir=data_dir,
        workspace_root=workspace_root,
        search_api_url=search_api_url,
        enable_code_execution=_read_bool("ENABLE_CODE_EXECUTION", False),
    )


def _read(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _read_positive_int(name: str, default: int) -> int:
    raw = _read(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigError(f"{name} 必须是正整数，当前值：{raw}") from error
    if value <= 0:
        raise ConfigError(f"{name} 必须是正整数，当前值：{raw}")
    return value


def _read_float(name: str, default: float) -> float:
    raw = _read(name, str(default))
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigError(f"{name} 必须是数字，当前值：{raw}") from error
    if not 0 <= value <= 1:
        raise ConfigError(f"{name} 必须在 0 到 1 之间")
    return value


def _read_bool(name: str, default: bool) -> bool:
    raw = _read(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} 必须是 true 或 false")


def _validate_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.fragment
    ):
        raise ConfigError(f"{name} 必须是有效 HTTP(S) URL")
