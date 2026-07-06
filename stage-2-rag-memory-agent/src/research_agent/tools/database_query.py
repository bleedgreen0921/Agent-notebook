"""只读查询工作区内 SQLite 数据库。"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..models import EvidenceSource, ToolResponse
from .base import ToolContext

_READ_QUERY = re.compile(r"^\s*(SELECT|WITH)\b", flags=re.IGNORECASE)


class DatabaseQueryTool:
    name = "database_query"
    description = "以只读模式查询工作区内的 SQLite 数据库，最多返回 100 行。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "database": {"type": "string", "description": "相对工作区的 .db 路径"},
            "query": {"type": "string", "description": "SELECT 或 WITH 查询"},
            "parameters": {"type": "array", "description": "位置参数列表"},
            "max_rows": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["database", "query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        if not isinstance(arguments, dict):
            return ToolResponse.error("database_query 参数必须是对象", "INVALID_ARGUMENTS")
        database = arguments.get("database")
        query = arguments.get("query")
        parameters = arguments.get("parameters", [])
        max_rows = arguments.get("max_rows", 50)
        if not isinstance(database, str) or not isinstance(query, str):
            return ToolResponse.error("database 和 query 必须是字符串", "INVALID_ARGUMENTS")
        if not isinstance(parameters, list):
            return ToolResponse.error("parameters 必须是数组", "INVALID_ARGUMENTS")
        if not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 1 <= max_rows <= 100:
            return ToolResponse.error("max_rows 必须在 1-100", "INVALID_ARGUMENTS")

        cleaned_query = query.strip().removesuffix(";").strip()
        if not _READ_QUERY.match(cleaned_query) or ";" in cleaned_query:
            return ToolResponse.error("只允许单条 SELECT 或 WITH 查询", "QUERY_DENIED")
        try:
            root = context.workspace_root.resolve(strict=True)
            path = (root / database).resolve(strict=True)
            path.relative_to(root)
        except (OSError, ValueError) as error:
            return ToolResponse.error(f"数据库路径无效或越界：{error}", "PATH_DENIED")
        if not path.is_file():
            return ToolResponse.error("数据库路径不是文件", "INVALID_DATABASE")

        uri = f"file:{quote(path.as_posix())}?mode=ro"
        try:
            context.raise_if_cancelled()
            with sqlite3.connect(uri, uri=True, timeout=3.0) as connection:
                connection.row_factory = sqlite3.Row
                # 长查询定期检查工具截止时间，使超时能够协作式中止。
                connection.set_progress_handler(
                    lambda: int(
                        context.cancel_event.is_set()
                        or time.monotonic() >= context.deadline
                    ),
                    1_000,
                )
                cursor = connection.execute(cleaned_query, parameters)
                rows = cursor.fetchmany(max_rows + 1)
                columns = [description[0] for description in cursor.description or []]
        except sqlite3.Error as error:
            return ToolResponse.error(f"SQLite 查询失败：{error}", "DATABASE_ERROR")
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        if not rows:
            return ToolResponse.empty("查询成功，但结果为空")
        data = {
            "columns": columns,
            "rows": [dict(row) for row in rows],
            "truncated": truncated,
        }
        source = EvidenceSource(
            title=path.name,
            uri=path.as_uri(),
            snippet=f"只读 SQL：{cleaned_query[:500]}",
            locator="SQLite 查询结果",
        )
        return ToolResponse.success(f"查询返回 {len(rows)} 行", data=data, sources=(source,))
