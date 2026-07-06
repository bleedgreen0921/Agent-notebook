# 小目标 2：让模型输出结构化 JSON（Python）

## 目标

把模型的自然语言响应限制为 Python 程序可判定的决策。每一步只能调用一个工具或返回最终答案。

## 输出协议

```json
{"type":"tool_call","tool_name":"calculator","arguments":{"expression":"2+2"}}
```

```json
{"type":"final","answer":"结果是 4。"}
```

## 实施计划

1. 使用两个 dataclass 表示 `FinalDecision` 与 `ToolCallDecision`。
2. 用 `|` 组成 `AgentDecision` 联合类型。
3. 调用 `registry.describe()` 动态获得工具说明。
4. 用 `json.dumps(..., ensure_ascii=False, indent=2)` 写入系统提示词。
5. 明确两种 JSON 示例、单工具限制、失败策略和数据边界。
6. 模型请求温度设为 `0.0`。
7. 若解析失败，向消息历史加入具体修正提示并继续下一步。

## 对应代码

- `src/minimal_agent/agent/prompt.py`
- `src/minimal_agent/agent/protocol.py`
- `src/minimal_agent/agent/loop.py`

## 关键决策

- 暂不绑定某个厂商的 `response_format` 或原生 function calling。
- `arguments` 必须直接是 JSON 对象，不能是包含 JSON 的字符串。
- 最终答案必须是非空字符串。
- 不要求模型输出思维链，只要求机器决策与最终用户答案。

## 验收标准

- [x] 两种结果由 `type` 字段明确区分。
- [x] 提示词中的工具列表来自当前注册表。
- [x] 每一步最多请求一个工具。
- [x] 错误结构不会直接进入工具层。
- [x] 协议错误可在剩余步骤内让模型修正。
- [ ] 在真实兼容模型上统计 JSON 格式成功率。
