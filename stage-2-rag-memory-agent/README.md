# Stage 2：RAG、工具调用与记忆研究助手（Python）

这是 `Plan.md` 第二阶段的独立实现。它在最小 Agent Loop 之上增加文档索引、向量检索、多类工具、三层记忆、重复调用防护和可验证引用，最终产出带来源链接的研究回答。

项目要求 Python 3.11+，运行时代码只使用标准库。

## 小目标与文档

| 小目标 | 实施文档 | 状态 |
| --- | --- | --- |
| chunk、embed、retrieve、answer with citations | [01-rag-pipeline.md](./docs/01-rag-pipeline.md) | 已编码 |
| 接入搜索、数据库、文件、浏览器、代码执行工具 | [02-tools.md](./docs/02-tools.md) | 已编码 |
| 区分短期上下文、会话记忆、长期记忆 | [03-memory.md](./docs/03-memory.md) | 已编码 |
| 处理失败、空结果、重复调用、幻觉引用 | [04-resilience.md](./docs/04-resilience.md) | 已编码 |
| 在回答中给出来源或证据 | [05-citations.md](./docs/05-citations.md) | 已编码 |

总体任务拆分和验收矩阵见 [00-implementation-plan.md](./docs/00-implementation-plan.md)。本次按环境约束只完成代码和静态审查，没有运行 Python、安装项目或调用外部 API。

逐模块学习源码时，可阅读 [06-code-walkthrough.md](./docs/06-code-walkthrough.md)。该文档详细解析 RAG、工具、三层记忆、证据引用和研究 Agent Loop 的完整数据流。

## 端到端流程

```text
index 文件
  ↓
chunk → embedding → SQLite 向量索引
                         │
用户研究问题              │
  ↓                      ↓
短期上下文 ← 会话记忆 ← 长期记忆召回
  ↓
Research Agent Loop
  ├─ rag_search / file_search / database_query
  ├─ web_search → browser_fetch
  ├─ python_code（默认关闭）
  └─ recall_memory / save_memory
          ↓
   证据账本分配 S1、S2…
          ↓
   引用校验 → 回答 + 来源链接
```

## 关键目录

```text
src/research_agent/
├── agent/       # 研究提示词、JSON 协议、核心循环
├── evidence/    # 来源登记和幻觉引用拦截
├── llm/         # OpenAI-compatible Chat Completions 客户端
├── memory/      # 短期、会话和长期记忆
├── rag/         # 分块、embedding、索引、向量检索
├── storage/     # SQLite schema 和连接管理
├── tools/       # 八个工具及统一注册表
├── config.py
├── main.py
└── models.py
```

## RAG 实现

- `TextChunker` 优先保留段落边界，默认每块 1200 字符、重叠 200 字符。
- 默认 `HashEmbeddingProvider` 不需要网络，适合学习数据流。
- 可切换 `OpenAIEmbeddingProvider` 调用兼容 `/embeddings` 接口。
- `SQLiteVectorStore` 保存文档、文本块、来源、定位信息和向量。
- `Retriever` 使用余弦相似度排序，并把命中片段转换为可引用来源。

本地哈希向量不等同于专业语义模型。切换 embedding provider 或维度后，应重新建立索引。

## 工具清单

| 工具 | 用途 | 主要边界 |
| --- | --- | --- |
| `rag_search` | 检索已索引资料 | top-k 与最低分数 |
| `web_search` | MediaWiki 网络搜索 | 响应大小、超时 |
| `browser_fetch` | 提取公开网页正文 | 拒绝内网/本机、限制类型与大小 |
| `file_search` | 工作区关键词搜索 | 路径、扩展名、文件大小 |
| `database_query` | 查询 SQLite | 只读连接、仅 SELECT/WITH、行数限制 |
| `python_code` | 受限数据计算 | 默认关闭、AST 白名单、隔离子进程 |
| `recall_memory` | 召回长期记忆 | namespace 隔离，不作为事实来源 |
| `save_memory` | 保存明确要求记住的信息 | 提示词限制为显式用户要求 |

`python_code` 不是通用安全沙箱。即使启用了 AST、内置函数、子进程和资源限制，也不应处理不可信租户代码；默认配置为关闭。

## 三层记忆

- 短期上下文：仅当前 Agent 运行有效，超出字符预算时保留系统提示和最新消息。
- 会话记忆：SQLite 中按 `session_id` 保存用户问题和最终回答，供下一轮延续对话。
- 长期记忆：按 `namespace` 隔离，保存 embedding，并按当前问题相关度召回。

检索资料属于外部证据；长期记忆只是用户上下文，不能冒充事实来源。

## 将来具备 Python 环境后的使用方式

```bash
cd stage-2-rag-memory-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .

export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="你的 API Key"
export LLM_MODEL="模型名"
export AGENT_WORKSPACE_ROOT=".."
```

先索引工作区资料：

```bash
research-agent index Plan.md stage-1-minimal-agent/docs
```

执行研究任务：

```bash
research-agent ask "比较 Stage 1 和 Stage 2 的能力边界" \
  --session learning --namespace user-1
```

显式保存长期记忆：

```bash
research-agent remember "我更容易理解带中文注释的 Python 示例" \
  --namespace user-1
```

不安装项目也可使用：

```bash
PYTHONPATH=src python3 -m research_agent.main ask "研究问题"
```

程序不会自动加载 `.env`，需要由 shell 导出变量。全部可选项见 `.env.example`。

## 回答与引用约束

工具来源被证据账本转换为当前任务局部编号 `S1`、`S2`。模型必须在事实后写 `[S1]`，并在 `citations` 数组声明相同编号。程序会拒绝不存在的编号、正文与数组不一致、已有证据却无引用的回答；验证通过后才输出真实来源 URL。

## 当前未执行的验证

- Python 语法和类型检查。
- SQLite 建库、索引、召回与迁移验证。
- 真实 LLM、embedding、MediaWiki 和网页请求。
- 超时、SSRF、代码执行及 prompt injection 的动态安全测试。
- 固定问题集上的引用正确率与检索质量评测。
