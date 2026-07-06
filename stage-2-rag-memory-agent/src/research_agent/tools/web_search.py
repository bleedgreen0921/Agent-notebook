"""通过 MediaWiki API 搜索公开网页。"""

from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from ..models import EvidenceSource, ToolResponse
from .base import ToolContext
from .html_utils import strip_html

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class WebSearchTool:
    name = "web_search"
    description = "通过公开 MediaWiki 搜索网络资料，返回标题、摘要和可引用链接。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, api_url: str, timeout_ms: int = 10_000) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms 必须大于 0")
        self._api_url = api_url
        self._timeout_ms = timeout_ms

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        if not isinstance(arguments, dict) or not isinstance(arguments.get("query"), str):
            return ToolResponse.error("web_search 需要字符串 query", "INVALID_ARGUMENTS")
        query = arguments["query"].strip()
        limit = arguments.get("max_results", 5)
        if not query or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            return ToolResponse.error("query 不能为空且 max_results 必须在 1-10", "INVALID_ARGUMENTS")

        separator = "&" if "?" in self._api_url else "?"
        params = urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "utf8": 1,
            }
        )
        request = Request(
            f"{self._api_url}{separator}{params}",
            headers={"User-Agent": "Stage2ResearchAgent/1.0", "Accept": "application/json"},
        )
        try:
            context.raise_if_cancelled()
            with urlopen(request, timeout=self._timeout_ms / 1_000) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            return ToolResponse.error(f"搜索服务 HTTP {error.code}", "SEARCH_HTTP_ERROR")
        except (URLError, TimeoutError, socket.timeout, OSError) as error:
            return ToolResponse.error(f"搜索服务不可用：{error}", "SEARCH_NETWORK_ERROR")
        if len(raw) > _MAX_RESPONSE_BYTES:
            return ToolResponse.error("搜索响应过大", "SEARCH_RESPONSE_TOO_LARGE")

        try:
            payload = json.loads(raw.decode("utf-8"))
            results = payload["query"]["search"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            return ToolResponse.error(f"搜索响应格式错误：{error}", "SEARCH_BAD_RESPONSE")
        if not isinstance(results, list) or not results:
            return ToolResponse.empty(f"网络搜索没有找到：{query}")

        parsed_api = urlparse(self._api_url)
        article_base = f"{parsed_api.scheme}://{parsed_api.netloc}/wiki/"
        items: list[dict[str, str]] = []
        sources: list[EvidenceSource] = []
        for item in results[:limit]:
            if not isinstance(item, dict) or not isinstance(item.get("title"), str):
                continue
            title = item["title"]
            snippet = strip_html(str(item.get("snippet", "")))[:1_000]
            url = article_base + quote(title.replace(" ", "_"))
            items.append({"title": title, "url": url, "snippet": snippet})
            sources.append(EvidenceSource(title, url, snippet or title))
        if not items:
            return ToolResponse.empty(f"网络搜索没有可用结果：{query}")
        return ToolResponse.success(
            f"网络搜索返回 {len(items)} 条结果", data=items, sources=sources
        )
