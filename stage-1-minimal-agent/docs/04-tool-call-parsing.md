# 小目标 4：解析模型的 tool call（Python）

## 目标

模型输出是不可信的外部数据。Python 程序必须先解析、再逐字段校验，最后才能决定是否调用工具。

## 实施计划

1. 对原始文本调用 `strip()`。
2. 用正则表达式容忍完整 JSON 外的一层 Markdown 代码围栏。
3. 使用 `json.loads()` 解析 JSON。
4. 使用 `isinstance(value, dict)` 确认根对象类型。
5. 检查字符串 `type`。
6. 对 `final` 检查非空字符串 `answer`。
7. 对 `tool_call` 检查非空 `tool_name` 和字典 `arguments`。
8. 返回对应 dataclass；非法情况抛出 `ProtocolError`。

## 对应代码

- `src/minimal_agent/agent/protocol.py`
- `src/minimal_agent/errors.py`

## 为什么类型标注不够

Python 的类型标注主要供阅读器和静态检查器使用，不会自动检查 `json.loads()` 返回的数据。即使函数声明返回 `ToolCallDecision`，仍必须用 `isinstance()` 验证 LLM 实际返回的每个字段。

协议层只确认 `arguments` 是字典。具体业务参数由工具再次验证，例如计算器会拒绝数字类型的 `expression`。这能保持协议层通用，并防止工具盲目信任模型。

## 验收样例

| 输入 | 结果 |
| --- | --- |
| 合法 `final` JSON | 返回 `FinalDecision` |
| 合法 `tool_call` JSON | 返回 `ToolCallDecision` |
| 完整 JSON 代码围栏 | 容忍并解析 |
| JSON 前后混有解释 | 拒绝 |
| `arguments` 是字符串 | 拒绝 |
| 未知 `type` | 拒绝 |
| 空 `answer` | 拒绝 |

## 验收标准

- [x] 外部 JSON 的关键字段全部经过运行时检查。
- [x] 非法响应不会触发工具。
- [x] 错误信息能够指导模型修正。
- [x] 仅容忍完整代码围栏，不从混杂文本中猜测 JSON。
- [ ] 在可运行环境中将验收样例实现为参数化测试。
