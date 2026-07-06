"""默认关闭、语法受限且在子进程运行的 Python 代码工具。"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from typing import Any

from ..models import ToolResponse
from .base import ToolContext

_MAX_CODE_CHARS = 10_000
_ALLOWED_CALLS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
    "len", "list", "max", "min", "print", "range", "round", "set",
    "sorted", "str", "sum", "tuple", "zip", "sqrt", "log", "exp",
}
_DENIED_NODES = (
    ast.Import, ast.ImportFrom, ast.Attribute, ast.ClassDef, ast.FunctionDef,
    ast.AsyncFunctionDef, ast.Lambda, ast.With, ast.AsyncWith, ast.Try,
    ast.Raise, ast.Global, ast.Nonlocal, ast.Delete, ast.Await, ast.Yield,
    ast.YieldFrom,
)

_RUNNER = r'''
import json, math, sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1000000, 1000000))
    if hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
except (ImportError, OSError, ValueError):
    pass
output = []
def safe_print(*values, sep=" ", end="\n"):
    text = sep.join(str(value) for value in values) + end
    if sum(len(item) for item in output) + len(text) > 20000:
        raise RuntimeError("输出超过 20000 字符")
    output.append(text)
safe = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "float": float, "int": int, "len": len,
    "list": list, "max": max, "min": min, "print": safe_print,
    "range": range, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "sqrt": math.sqrt, "log": math.log, "exp": math.exp,
}
namespace = {"__builtins__": {}, **safe}
try:
    code = sys.stdin.read()
    exec(compile(code, "<agent-code>", "exec"), namespace, namespace)
    print(json.dumps({"ok": True, "stdout": "".join(output)}, ensure_ascii=False))
except Exception as error:
    print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False))
'''


class RestrictedPythonTool:
    name = "python_code"
    description = "执行无导入、无文件/网络访问的受限 Python 数据计算；默认关闭。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
        "additionalProperties": False,
    }

    def __init__(self, *, enabled: bool, timeout_ms: int = 3_000) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms 必须大于 0")
        self._enabled = enabled
        self._timeout_ms = timeout_ms

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        if not self._enabled:
            return ToolResponse.error("代码执行工具未启用", "CODE_EXECUTION_DISABLED")
        if not isinstance(arguments, dict) or not isinstance(arguments.get("code"), str):
            return ToolResponse.error("python_code 需要字符串 code", "INVALID_ARGUMENTS")
        code = arguments["code"].strip()
        if not code or len(code) > _MAX_CODE_CHARS:
            return ToolResponse.error("code 不能为空且不能超过 10000 字符", "INVALID_ARGUMENTS")
        validation_error = _validate_code(code)
        if validation_error:
            return ToolResponse.error(validation_error, "CODE_DENIED")

        context.raise_if_cancelled()
        timeout_seconds = min(
            self._timeout_ms / 1_000,
            max(0.1, context.deadline - time.monotonic()),
        )
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-c", _RUNNER],
                input=code,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResponse.error("代码执行超时", "CODE_TIMEOUT")
        except OSError as error:
            return ToolResponse.error(f"无法启动代码子进程：{error}", "CODE_PROCESS_ERROR")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return ToolResponse.error("代码子进程返回格式错误", "CODE_BAD_RESPONSE")
        if not isinstance(payload, dict):
            return ToolResponse.error("代码子进程返回类型错误", "CODE_BAD_RESPONSE")
        if not payload.get("ok"):
            return ToolResponse.error(str(payload.get("error", "代码执行失败")), "CODE_RUNTIME_ERROR")
        return ToolResponse.success("受限代码执行完成", data={"stdout": payload.get("stdout", "")})


def _validate_code(code: str) -> str | None:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        return f"Python 语法错误：{error.msg}"
    for node in ast.walk(tree):
        if isinstance(node, _DENIED_NODES):
            return f"不允许的 Python 语法：{type(node).__name__}"
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            return "不允许访问下划线开头的名称"
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
                return "只允许调用白名单中的纯计算函数"
    return None
