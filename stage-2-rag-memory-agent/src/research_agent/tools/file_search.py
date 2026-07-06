"""在工作区文本文件中进行精确关键词搜索。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import EvidenceSource, ToolResponse
from .base import ToolContext

_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".json", ".py"}
_MAX_FILE_BYTES = 512 * 1024


class FileSearchTool:
    name = "file_search"
    description = "按关键词搜索工作区内的 UTF-8 文本文件，适合查找精确名称或术语。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "path": {"type": "string", "description": "相对工作区目录，默认 ."},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        if not isinstance(arguments, dict) or not isinstance(arguments.get("query"), str):
            return ToolResponse.error("file_search 需要字符串 query", "INVALID_ARGUMENTS")
        query = arguments["query"].strip()
        raw_path = arguments.get("path", ".")
        limit = arguments.get("max_results", 10)
        if not query or not isinstance(raw_path, str):
            return ToolResponse.error("query 不能为空且 path 必须是字符串", "INVALID_ARGUMENTS")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            return ToolResponse.error("max_results 必须在 1-20", "INVALID_ARGUMENTS")

        try:
            root = context.workspace_root.resolve(strict=True)
            target = (root / raw_path).resolve(strict=True)
            target.relative_to(root)
        except (OSError, ValueError) as error:
            return ToolResponse.error(f"搜索路径无效或越界：{error}", "PATH_DENIED")

        files = [target] if target.is_file() else sorted(target.rglob("*"))
        matches: list[dict[str, object]] = []
        sources: list[EvidenceSource] = []
        needle = query.casefold()
        for path in files:
            context.raise_if_cancelled()
            if len(matches) >= limit:
                break
            try:
                actual_path = path.resolve(strict=True)
                actual_path.relative_to(root)
            except (OSError, ValueError):
                # 忽略指向工作区之外的符号链接。
                continue
            if not actual_path.is_file() or actual_path.suffix.lower() not in _EXTENSIONS:
                continue
            try:
                if actual_path.stat().st_size > _MAX_FILE_BYTES:
                    continue
                with actual_path.open("rb") as file:
                    raw = file.read(_MAX_FILE_BYTES + 1)
                if len(raw) > _MAX_FILE_BYTES:
                    continue
                lines = raw.decode("utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, start=1):
                if needle not in line.casefold():
                    continue
                relative = actual_path.relative_to(root).as_posix()
                snippet = line.strip()[:500]
                matches.append({"path": relative, "line": line_number, "text": snippet})
                sources.append(
                    EvidenceSource(
                        title=relative,
                        uri=actual_path.as_uri(),
                        snippet=snippet,
                        locator=f"第 {line_number} 行",
                    )
                )
                if len(matches) >= limit:
                    break
        if not matches:
            return ToolResponse.empty(f"没有找到关键词：{query}")
        return ToolResponse.success(
            f"找到 {len(matches)} 条文件匹配", data=matches, sources=sources
        )
