"""带基础 SSRF 防护的公开网页正文提取工具。"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..models import EvidenceSource, ToolResponse
from .base import ToolContext
from .html_utils import HTMLTextExtractor

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_TEXT_CHARS = 20_000


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        target = urljoin(req.full_url, newurl)
        _validate_public_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


class BrowserFetchTool:
    name = "browser_fetch"
    description = "打开公开 HTTP(S) 网页并提取正文；拒绝本机、内网和过大响应。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
        "additionalProperties": False,
    }

    def __init__(self, timeout_ms: int = 12_000) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms 必须大于 0")
        self._timeout_ms = timeout_ms
        self._opener = build_opener(_SafeRedirectHandler())

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        if not isinstance(arguments, dict) or not isinstance(arguments.get("url"), str):
            return ToolResponse.error("browser_fetch 需要字符串 url", "INVALID_ARGUMENTS")
        url = arguments["url"].strip()
        try:
            _validate_public_url(url)
        except ValueError as error:
            return ToolResponse.error(str(error), "URL_DENIED")

        request = Request(
            url,
            headers={
                "User-Agent": "Stage2ResearchAgent/1.0",
                "Accept": "text/html,text/plain,application/json",
            },
        )
        try:
            context.raise_if_cancelled()
            with self._opener.open(request, timeout=self._timeout_ms / 1_000) as response:
                final_url = response.geturl()
                _validate_public_url(final_url)
                content_type = response.headers.get_content_type()
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            return ToolResponse.error(f"网页返回 HTTP {error.code}", "BROWSER_HTTP_ERROR")
        except (URLError, TimeoutError, socket.timeout, OSError, ValueError) as error:
            return ToolResponse.error(f"网页访问失败：{error}", "BROWSER_NETWORK_ERROR")
        if len(raw) > _MAX_RESPONSE_BYTES:
            return ToolResponse.error("网页响应超过 2 MiB", "BROWSER_RESPONSE_TOO_LARGE")
        if content_type not in {"text/html", "text/plain", "application/json"}:
            return ToolResponse.error(f"不支持的内容类型：{content_type}", "UNSUPPORTED_CONTENT")

        try:
            decoded = raw.decode(charset, errors="replace")
        except LookupError:
            decoded = raw.decode("utf-8", errors="replace")
        if content_type == "text/html":
            parser = HTMLTextExtractor()
            parser.feed(decoded)
            title = parser.title.strip() or urlparse(final_url).netloc
            text = parser.text()
        else:
            title = urlparse(final_url).netloc
            text = decoded.strip()
        text = text[:_MAX_TEXT_CHARS]
        if not text:
            return ToolResponse.empty("网页没有提取到正文")
        source = EvidenceSource(title, final_url, text[:4_000])
        return ToolResponse.success(
            f"已提取网页正文，共 {len(text)} 字符",
            data={"title": title, "url": final_url, "text": text},
            sources=(source,),
        )


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("只允许完整的 HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("URL 不允许包含用户名或密码")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(
            parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as error:
        raise ValueError(f"无法解析网页域名：{error}") from error
    if not addresses:
        raise ValueError("网页域名没有可用地址")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("拒绝访问本机、内网或保留地址")
