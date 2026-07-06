# 小目标 1：使用 LLM API 完成普通对话（Python）

## 目标

先将“调用模型”实现为独立 Python 能力，再交给 Agent Loop 复用。LLM 客户端不应了解工具、循环步骤或 Agent 状态。

## 实施计划

1. 使用 `@dataclass` 定义不可变的 `ChatMessage`。
2. 使用 `typing.Protocol` 定义 `LLMClient.complete()` 接口。
3. 使用 `urllib.request.Request` 构造 POST 请求。
4. 从环境变量取得 URL、API Key、模型名和超时。
5. 使用 `json.dumps()` 编码请求，保留中文字符。
6. 处理 HTTP 错误、网络错误、socket 超时、过大响应和非法 UTF-8 JSON。
7. 逐层检查 `choices[0].message.content`。
8. 使用 `SimpleChatSession` 保存多轮消息；失败时撤销本轮用户消息。
9. 在 CLI 中提供 `--chat` 入口。

## 对应代码

- `src/minimal_agent/models.py`
- `src/minimal_agent/config.py`
- `src/minimal_agent/llm/openai_compatible_client.py`
- `src/minimal_agent/chat/simple_chat.py`

## 需要理解的 Python 语法

- `@dataclass(frozen=True, slots=True)`：自动生成初始化函数，并防止消息对象被随意修改。
- `Protocol`：只要对象提供约定的方法，就可以作为 LLM 客户端使用。
- `with urlopen(...) as response`：用完响应后自动关闭网络资源。
- `raise ... from error`：保留原始异常原因，同时提供项目自己的错误文本。
- `try/except`：区分可预期的 HTTP、网络、超时和解析错误。

## 关键边界

- API Key 只进入 HTTP `Authorization` 头，不进入日志。
- 响应最多读取 2 MiB，防止异常服务耗尽内存。
- `content` 可以是字符串，也兼容常见 text-part 数组。
- 普通会话的 `history` 返回 tuple，调用者不能增删内部消息。

## 验收标准

- [x] 普通对话和 Agent 共用一个 `LLMClient` 接口。
- [x] 请求使用标准 Chat Completions 消息格式。
- [x] 成功响应必须产生非空文本。
- [x] 失败请求不保留在会话历史中。
- [x] 运行时无第三方 HTTP 依赖。
- [ ] 在可用 Python 与 API 环境中进行真实请求验证。
