"""网页工具共用的轻量 HTML 文本提取器。"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title += data
        self._parts.append(data)

    def text(self) -> str:
        joined = " ".join(self._parts)
        joined = re.sub(r"[ \t\f\v]+", " ", joined)
        joined = re.sub(r"\n\s*\n+", "\n\n", joined)
        return joined.strip()


def strip_html(value: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(unescape(value))
    return parser.text()
