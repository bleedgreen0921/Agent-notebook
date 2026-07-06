"""从环境变量读取应用配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ConfigError


@dataclass(frozen=True, slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_ms: int


@dataclass(frozen=True, slots=True)
class AgentConfig:
    max_steps: int
    timeout_ms: int
    tool_timeout_ms: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    llm: LLMConfig
    agent: AgentConfig


def _read_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"缺少必需环境变量：{name}")
    return value


def _read_positive_integer(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigError(f"{name} 必须是正整数，当前值为：{raw}") from error
    if value <= 0:
        raise ConfigError(f"{name} 必须是正整数，当前值为：{raw}")
    return value


def load_config() -> AppConfig:
    """读取并验证全部配置，使问题在启动阶段尽早暴露。"""

    base_url = _read_required("LLM_BASE_URL").rstrip("/")
    parsed_url = urlparse(base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ConfigError("LLM_BASE_URL 必须是有效的 HTTP(S) 地址")

    return AppConfig(
        llm=LLMConfig(
            base_url=base_url,
            api_key=_read_required("LLM_API_KEY"),
            model=_read_required("LLM_MODEL"),
            timeout_ms=_read_positive_integer("LLM_TIMEOUT_MS", 30_000),
        ),
        agent=AgentConfig(
            max_steps=_read_positive_integer("AGENT_MAX_STEPS", 8),
            timeout_ms=_read_positive_integer("AGENT_TIMEOUT_MS", 120_000),
            tool_timeout_ms=_read_positive_integer("TOOL_TIMEOUT_MS", 10_000),
        ),
    )
