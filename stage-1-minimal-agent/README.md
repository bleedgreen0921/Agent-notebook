# Stage 1：最小 Agent Loop（Python）

这是 `Plan.md` 第一阶段的 Python 实现。项目要求 Python 3.11 或更高版本，只使用 Python 标准库，不依赖模型厂商 SDK 或其他运行时第三方包。

## 实现状态

| 小目标 | 实施文档 | 主要代码 | 状态 |
| --- | --- | --- | --- |
| 使用 LLM API 完成普通对话 | [01-llm-chat.md](./docs/01-llm-chat.md) | `src/minimal_agent/llm/`、`chat/` | 已编码 |
| 让模型输出结构化 JSON | [02-structured-output.md](./docs/02-structured-output.md) | `agent/prompt.py` | 已编码 |
| 定义工具函数 | [03-tool-definition.md](./docs/03-tool-definition.md) | `src/minimal_agent/tools/` | 已编码 |
| 解析模型的 tool call | [04-tool-call-parsing.md](./docs/04-tool-call-parsing.md) | `agent/protocol.py` | 已编码 |
| 执行工具并把结果喂回模型 | [05-tool-execution-loop.md](./docs/05-tool-execution-loop.md) | `agent/loop.py` | 已编码 |
| 最大步数、超时和错误处理 | [06-guardrails.md](./docs/06-guardrails.md) | `errors.py`、`agent/loop.py` | 已编码 |

完整任务拆分和验收矩阵见 [00-implementation-plan.md](./docs/00-implementation-plan.md)。按照当前环境约束，本次只完成代码迁移和静态审查，没有运行 Python、安装项目或调用 LLM。

逐模块学习源码时，可阅读 [07-code-walkthrough.md](./docs/07-code-walkthrough.md)。该文档包含完整执行流程、Python 语法说明和代码设计分析。

## 工作原理

```text
用户任务
   ↓
Agent Loop ──请求──> LLM API
   ↑                    │
   │                    ├─ final JSON ──> 最终答案
   │                    │
   │                    └─ tool_call JSON
   │                              ↓
   └──工具结果── Tool Registry ──> calculator / read_file
```

模型每一步只能返回两种 JSON：

```json
{"type":"tool_call","tool_name":"calculator","arguments":{"expression":"(12+8)/4"}}
```

```json
{"type":"final","answer":"计算结果是 5。"}
```

Agent 校验响应，执行工具，再把结果作为一条新消息送回模型，直到得到 `final`，或触发步骤、时间限制。

## Python 文件结构

```text
stage-1-minimal-agent/
├── docs/                              # 六个小目标的详细实施计划
├── src/minimal_agent/
│   ├── agent/
│   │   ├── loop.py                    # 核心 Agent Loop
│   │   ├── prompt.py                  # 结构化输出提示词
│   │   └── protocol.py                # JSON 决策解析与校验
│   ├── chat/simple_chat.py            # 普通多轮对话
│   ├── llm/openai_compatible_client.py# LLM HTTP 客户端
│   ├── tools/
│   │   ├── base.py                    # 工具接口和公共类型
│   │   ├── registry.py                # 工具注册与限时执行
│   │   ├── calculator.py              # 安全四则运算
│   │   └── read_file.py               # 受限文件读取
│   ├── config.py                      # 环境变量配置
│   ├── errors.py                      # 统一错误类型
│   ├── main.py                        # CLI 入口
│   └── models.py                      # 消息和 LLM 接口
├── .env.example
└── pyproject.toml
```

## 推荐阅读顺序

如果不熟悉 Python，建议按以下顺序阅读：

1. `models.py`：了解 `dataclass` 和 `Protocol` 表示的数据结构。
2. `simple_chat.py`：查看最简单的“保存消息 → 请求模型 → 保存回答”。
3. `base.py`、`calculator.py`：了解工具接口与具体实现。
4. `protocol.py`：查看如何把不可信 JSON 转换成程序决策。
5. `loop.py`：理解完整 Agent 循环。
6. `main.py`：查看配置、组件组装和命令行入口。

## 配置与运行方式

以下命令供以后具备 Python 3.11+ 环境时使用，本次未执行。

```bash
cd stage-1-minimal-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .

export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="你的 API Key"
export LLM_MODEL="支持 Chat Completions 的模型名"
```

普通对话模式：

```bash
minimal-agent --chat "用一句话解释什么是 Agent Loop"
```

Agent 模式：

```bash
minimal-agent "计算 (125 + 75) / 8"
minimal-agent "读取 README.md 并概括其内容"
```

也可以不安装项目，临时设置源码路径后运行：

```bash
PYTHONPATH=src python3 -m minimal_agent.main "计算 2 + 2"
```

可选配置见 `.env.example`。程序不会自动读取 `.env` 文件，需要通过 shell 导出变量。`read_file` 默认只能访问启动目录，也可通过 `AGENT_WORKSPACE_ROOT` 显式设置边界。

## 当前边界

- 使用提示词约定的 JSON 工具协议，没有绑定厂商专属 function calling。
- 每一步只允许一个工具调用，便于观察循环状态。
- 只提供四则运算和受目录限制的 UTF-8 文本读取工具。
- 消息历史仅存在内存中，不提供持久化、RAG 或长期记忆。
- Python 线程超时采用协作式取消，不能强制杀死不响应取消信号的第三方工具。
- 尚未进行语法、类型或真实 API 测试；首次运行前应先执行基本检查。

例如，安装项目后可先执行标准库语法检查：

```bash
python3 -m compileall -q src
```
