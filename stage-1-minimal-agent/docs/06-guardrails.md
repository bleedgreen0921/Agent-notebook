# 小目标 6：最大步数、超时和错误处理（Python）

## 目标

确保 Agent 面对错误 JSON、慢请求、错误参数和工具故障时，可以在明确边界内结束。

## 最大步骤数

- `AGENT_MAX_STEPS` 默认 8。
- 每次 LLM 决策计为一步，格式修正也消耗步骤。
- 用尽步骤仍没有 `final` 时抛出 `MAX_STEPS`。

## 分层超时

- `LLM_TIMEOUT_MS`：普通对话的默认超时，也是 Agent 单次 LLM 请求上限。
- `TOOL_TIMEOUT_MS`：单次工具执行等待上限，默认 10 秒。
- `AGENT_TIMEOUT_MS`：整个 Agent 的总时限，默认 120 秒。
- Agent 中每次 LLM 和工具调用都取自身限制与总剩余时间的较小值。
- 时间计算使用 `time.monotonic()`，不受系统时钟跳变影响。

## 错误分类

| 类型 | 用途 | 是否终止 Agent |
| --- | --- | --- |
| `ConfigError` | 缺少或错误配置 | 是 |
| `LLMError` | HTTP、网络、超时或响应错误 | 是 |
| `ProtocolError` | 模型 JSON 不符合协议 | 否，要求模型修正 |
| `ToolError` | 参数、权限或工具执行错误 | 否，作为失败结果回填 |
| `AgentLimitError` | 达到步骤或总时间限制 | 是 |

## 可观测性

- `AgentEvent` 记录步骤开始、模型输出、协议错误、工具结束和 Agent 完成。
- CLI 仅显示步骤、错误摘要、工具状态及耗时。
- 默认日志不输出 API Key、认证头或完整系统提示词。

## 对应代码

- `src/minimal_agent/config.py`
- `src/minimal_agent/errors.py`
- `src/minimal_agent/llm/openai_compatible_client.py`
- `src/minimal_agent/tools/registry.py`
- `src/minimal_agent/agent/loop.py`
- `src/minimal_agent/main.py`

## Python 超时的已知限制

- `urllib` 的 timeout 主要限制阻塞网络操作，不是能够杀死函数的硬性墙钟计时器。Agent 会在请求返回后再次检查总截止时间。
- `ThreadPoolExecutor` 可以让主循环在超时后停止等待，但 Python 不能安全强制终止正在运行的线程。注册表会设置 `Event`，工具需要主动检查它。
- 当前两个工具都很短，并在关键位置检查取消状态。未来接入长任务时，应在循环、网络分页或文件分块中频繁检查取消事件。
- 暂不自动重试 LLM 请求，避免重复计费和掩盖配置错误。

## 验收标准

- [x] 步数及三层超时均可配置且必须为正整数。
- [x] 总剩余时间限制每次 LLM 和工具调用。
- [x] 可恢复错误回填模型，不可恢复错误退出。
- [x] CLI 把异常转成清晰文本和非零退出码。
- [x] 默认日志不泄露密钥。
- [ ] 在可运行环境中验证超时、步骤耗尽和错误码。
