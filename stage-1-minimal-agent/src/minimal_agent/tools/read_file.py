"""受工作区边界限制的 UTF-8 文本读取工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import ToolError
from .base import ToolContext

_MAX_FILE_BYTES = 100 * 1024


class ReadFileTool:
    name = "read_file"
    description = "读取当前工作区内的 UTF-8 文本文件，最大 100 KiB。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "相对于工作区根目录的文件路径，例如 Plan.md",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def execute(self, arguments: object, context: ToolContext) -> object:
        context.raise_if_cancelled()
        if not isinstance(arguments, dict) or not isinstance(
            arguments.get("path"), str
        ):
            raise ToolError("read_file 参数必须包含字符串 path")

        raw_path = arguments["path"].strip()
        if not raw_path:
            raise ToolError("path 不能为空")
        if "\x00" in raw_path:
            raise ToolError("文件路径包含非法空字符")

        try:
            root = context.workspace_root.resolve(strict=True)
        except FileNotFoundError as error:
            raise ToolError("工作区根目录不存在") from error
        except OSError as error:
            raise ToolError(f"无法解析工作区根目录：{error}") from error
        if not root.is_dir():
            raise ToolError("工作区根路径不是目录")

        try:
            requested_path = Path(raw_path)
            if not requested_path.is_absolute():
                requested_path = root / requested_path
            actual_path = requested_path.resolve(strict=True)
            relative_path = actual_path.relative_to(root)
        except ValueError as error:
            raise ToolError("拒绝读取工作区之外的文件") from error
        except FileNotFoundError as error:
            raise ToolError(f"文件不存在：{raw_path}") from error
        except OSError as error:
            raise ToolError(f"无法解析文件路径：{error}") from error

        try:
            if not actual_path.is_file():
                raise ToolError("目标路径不是普通文件")
            file_size = actual_path.stat().st_size
        except OSError as error:
            raise ToolError(f"无法检查文件：{error}") from error
        if file_size > _MAX_FILE_BYTES:
            raise ToolError(f"文件超过 {_MAX_FILE_BYTES} 字节限制")

        context.raise_if_cancelled()
        try:
            # 即使文件在 stat 后被替换，也最多读取上限加一个字节。
            with actual_path.open("rb") as file:
                content_bytes = file.read(_MAX_FILE_BYTES + 1)
            if len(content_bytes) > _MAX_FILE_BYTES:
                raise ToolError(f"文件超过 {_MAX_FILE_BYTES} 字节限制")
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("文件不是合法的 UTF-8 文本") from error
        except OSError as error:
            raise ToolError(f"读取文件失败：{error}") from error
        context.raise_if_cancelled()

        return {
            "path": relative_path.as_posix(),
            "bytes": len(content_bytes),
            "content": content,
        }
