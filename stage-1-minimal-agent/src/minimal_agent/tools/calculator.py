"""不执行任意 Python 代码的安全四则运算工具。"""

from __future__ import annotations

import math
import re
from typing import Any

from ..errors import ToolError
from .base import ToolContext

_NUMBER_PATTERN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")


class CalculatorTool:
    """仅支持数字、括号及 +、-、*、/ 的表达式计算器。"""

    name = "calculator"
    description = "计算只包含数字、括号及 + - * / 的数学表达式。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "例如：(12.5 + 7.5) / 4",
            }
        },
        "required": ["expression"],
        "additionalProperties": False,
    }

    def execute(self, arguments: object, context: ToolContext) -> object:
        context.raise_if_cancelled()
        if not isinstance(arguments, dict) or not isinstance(
            arguments.get("expression"), str
        ):
            raise ToolError("calculator 参数必须包含字符串 expression")

        expression = arguments["expression"].strip()
        if not expression:
            raise ToolError("expression 不能为空")
        if len(expression) > 500:
            raise ToolError("expression 长度不能超过 500")

        value = _ExpressionParser(expression).parse()
        if not math.isfinite(value):
            raise ToolError("计算结果不是有限数值")

        # 整数结果去掉无意义的小数点，便于用户阅读。
        readable_value: int | float = int(value) if value.is_integer() else value
        return {"expression": expression, "value": readable_value}


class _ExpressionParser:
    """递归下降解析器：expression -> term -> unary -> primary。"""

    def __init__(self, source: str) -> None:
        self._source = source
        self._position = 0

    def parse(self) -> float:
        value = self._parse_expression()
        self._skip_whitespace()
        if self._position != len(self._source):
            raise ToolError(f"表达式在位置 {self._position} 包含非法内容")
        return value

    def _parse_expression(self) -> float:
        value = self._parse_term()
        while True:
            if self._consume("+"):
                value += self._parse_term()
            elif self._consume("-"):
                value -= self._parse_term()
            else:
                return value

    def _parse_term(self) -> float:
        value = self._parse_unary()
        while True:
            if self._consume("*"):
                value *= self._parse_unary()
            elif self._consume("/"):
                divisor = self._parse_unary()
                if divisor == 0:
                    raise ToolError("不能除以零")
                value /= divisor
            else:
                return value

    def _parse_unary(self) -> float:
        if self._consume("+"):
            return self._parse_unary()
        if self._consume("-"):
            return -self._parse_unary()
        return self._parse_primary()

    def _parse_primary(self) -> float:
        if self._consume("("):
            value = self._parse_expression()
            if not self._consume(")"):
                raise ToolError(f"位置 {self._position} 缺少右括号")
            return value
        return self._parse_number()

    def _parse_number(self) -> float:
        self._skip_whitespace()
        match = _NUMBER_PATTERN.match(self._source, self._position)
        if match is None:
            raise ToolError(f"位置 {self._position} 应为数字")
        self._position = match.end()
        return float(match.group())

    def _consume(self, expected: str) -> bool:
        self._skip_whitespace()
        if self._position >= len(self._source):
            return False
        if self._source[self._position] != expected:
            return False
        self._position += 1
        return True

    def _skip_whitespace(self) -> None:
        while (
            self._position < len(self._source)
            and self._source[self._position].isspace()
        ):
            self._position += 1
