# Stage 2 实现与代码详细解析

## 1. Stage 2 在 Stage 1 上增加了什么

Stage 1 的核心流程是：

```text
LLM 决策 → 调用工具 → 回填结果 → LLM 继续决策
```

Stage 2 将其扩展成资料研究系统：

```text
资料索引
  ↓
chunk → embedding → SQLite 向量库
                         │
用户研究问题              │
  ↓                      ↓
会话记忆 + 长期记忆 → Research Agent
                         ├─ 本地 RAG
                         ├─ 文件搜索
                         ├─ 数据库查询
                         ├─ 网络搜索
                         ├─ 网页抓取
                         ├─ 受限代码执行
                         └─ 记忆读写
                                ↓
                         Evidence Ledger
                                ↓
                          引用校验与回答
```

| 能力 | Stage 1 | Stage 2 |
| --- | --- | --- |
| 工具数量 | 2 个简单工具 | 8 个研究工具 |
| 工具结果 | 成功或失败 | success、empty、error |
| RAG | 无 | 完整索引和检索管线 |
| 记忆 | 当前消息列表 | 短期、会话、长期三层 |
| 重复调用 | 只靠最大步骤 | 参数指纹拦截 |
| 引用 | 无 | 证据账本和引用校验 |
| 持久化 | 无 | SQLite |
| 最终输出 | 普通答案 | 答案、`[Sx]`、来源链接 |

核心循环位于 `src/research_agent/agent/loop.py`。

## 2. 项目结构

```text
stage-2-rag-memory-agent/
├── pyproject.toml
├── .env.example
└── src/research_agent/
    ├── main.py
    ├── config.py
    ├── errors.py
    ├── models.py
    ├── llm/
    │   └── openai_compatible_client.py
    ├── storage/
    │   └── database.py
    ├── rag/
    │   ├── models.py
    │   ├── chunker.py
    │   ├── embeddings.py
    │   ├── vector_store.py
    │   ├── indexer.py
    │   └── retriever.py
    ├── memory/
    │   ├── short_term.py
    │   ├── session.py
    │   └── long_term.py
    ├── tools/
    │   ├── base.py
    │   ├── registry.py
    │   ├── rag_search.py
    │   ├── file_search.py
    │   ├── database_query.py
    │   ├── web_search.py
    │   ├── browser_fetch.py
    │   ├── code_execution.py
    │   └── memory_tools.py
    ├── evidence/
    │   ├── ledger.py
    │   └── validator.py
    └── agent/
        ├── prompt.py
        ├── protocol.py
        └── loop.py
```

模块关系：

```text
配置、公共模型、错误
        ↓
SQLite 存储
  ├── RAG 索引
  ├── 会话记忆
  └── 长期记忆

RAG + 网络 + 文件 + 数据库 + 代码 + 记忆
                    ↓
                 工具注册表
                    ↓
                 Agent Loop
                    ↓
          证据账本 → 引用校验
                    ↓
                 CLI 输出
```

## 3. CLI 的三种模式

入口位于 `src/research_agent/main.py`。

### 3.1 index：建立 RAG 索引

```bash
research-agent index Plan.md docs/
```

流程：

```text
路径
  ↓
遍历文件
  ↓
检查工作区、类型、大小、UTF-8
  ↓
计算内容哈希
  ↓
分块
  ↓
生成 embedding
  ↓
写入 SQLite
```

组件组装：

```python
indexer = DocumentIndexer(
    workspace_root=config.workspace_root,
    chunker=TextChunker(),
    embeddings=embeddings,
    vector_store=vector_store,
)
```

索引结果分别统计新增或更新、未变化、跳过和错误文件。

### 3.2 ask：执行研究任务

```bash
research-agent ask "比较 Stage 1 和 Stage 2"
```

流程：

```text
创建 Retriever
  ↓
创建 LLM 客户端
  ↓
注册全部工具
  ↓
创建 ResearchAgent
  ↓
加载会话和长期记忆
  ↓
执行研究循环
  ↓
输出回答和来源
```

### 3.3 remember：显式写入长期记忆

```bash
research-agent remember "用户喜欢中文注释" --namespace user-1
```

该命令不需要 LLM，直接调用 `LongTermMemoryStore.save()`。

## 4. 配置系统

代码位于 `src/research_agent/config.py`。

### 4.1 LLMConfig

```python
@dataclass(frozen=True, slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_ms: int
```

保存 Chat Completions API 地址、认证、模型和超时。

### 4.2 EmbeddingConfig

```python
@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    provider: str
    model: str
    dimensions: int
```

支持两种 provider：

```text
local  → HashEmbeddingProvider
openai → OpenAIEmbeddingProvider
```

### 4.3 AgentConfig

```python
@dataclass(frozen=True, slots=True)
class AgentConfig:
    max_steps: int
    timeout_ms: int
    tool_timeout_ms: int
    context_max_chars: int
    retrieval_top_k: int
    retrieval_min_score: float
```

Stage 2 新增上下文字符预算、默认检索数量和最低相似度。

### 4.4 require_llm

`load_config(require_llm=True)` 允许 CLI 根据命令决定是否强制要求 LLM 配置。

`ask` 必须调用 LLM；使用本地 embedding 时，`index` 和 `remember` 不需要 LLM API Key。

## 5. 公共数据模型

代码位于 `src/research_agent/models.py`。

### 5.1 ChatMessage 和 LLMClient

`ChatMessage` 与 Stage 1 相同，包含 system、user、assistant 三种角色。`LLMClient` 使用 Protocol，使 ResearchAgent 不依赖特定模型实现。

### 5.2 EvidenceSource

```python
@dataclass(frozen=True, slots=True)
class EvidenceSource:
    title: str
    uri: str
    snippet: str
    locator: str | None = None
```

它表示工具返回的原始证据，例如：

```python
EvidenceSource(
    title="Plan.md",
    uri="file:///project/Plan.md",
    snippet="Stage 2：学习工具调用、RAG与记忆",
    locator="第 23 行",
)
```

此时证据还没有 `S1` 编号。

### 5.3 RegisteredSource

```python
@dataclass(frozen=True, slots=True)
class RegisteredSource:
    source_id: str
    title: str
    uri: str
    snippet: str
    locator: str | None = None
```

它表示证据已进入当前任务的证据账本：

```text
EvidenceSource
      ↓ EvidenceLedger.register()
RegisteredSource(source_id="S1")
```

### 5.4 ToolResponse 三态结果

```python
@dataclass(frozen=True, slots=True)
class ToolResponse:
    status: Literal["success", "empty", "error"]
    summary: str
    data: object | None = None
    sources: tuple[EvidenceSource, ...] = ()
    error_code: str | None = None
```

三种状态的含义：

| 状态 | 含义 | Agent 后续行为 |
| --- | --- | --- |
| `success` | 工具完成并返回数据 | 使用数据和证据 |
| `empty` | 工具正常但没有匹配 | 修改查询或更换来源 |
| `error` | 参数、权限、网络或执行错误 | 修正参数或说明限制 |

`empty` 不能伪装成错误，也不能被模型当作证据。

## 6. SQLite 统一存储

代码位于 `src/research_agent/storage/database.py`。

一个 SQLite 数据库同时存储 RAG 文档、文本块、会话消息和长期记忆。

### 6.1 documents

```sql
CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

`content_hash` 用于判断文件内容是否发生变化。

### 6.2 rag_chunks

```sql
CREATE TABLE rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    locator TEXT
);
```

每个 chunk 保存文本、JSON 向量和定位信息。

### 6.3 session_messages

按 `session_id` 保存用户问题和通过验证的最终回答。

### 6.4 long_term_memories

按 namespace 保存长期内容、metadata、embedding 和时间。

### 6.5 独立连接与事务

每次数据库操作创建独立 connection。这避免在线程池工具中共享同一个 SQLite connection。

写操作使用：

```python
BEGIN IMMEDIATE
  ↓
执行写入
  ↓
成功 commit / 失败 rollback
```

这样不会留下只写入一半的文档或记忆。

## 7. RAG 数据模型

代码位于 `src/research_agent/rag/models.py`。

### 7.1 TextDocument

保存稳定 document ID、标题、来源 URI、正文和内容哈希。

### 7.2 TextChunk

保存 chunk 序号、文本和类似 `字符 1000-2200` 的定位信息。

### 7.3 RetrievalHit

检索结果同时包含 chunk、文档、来源、定位和相似度。

## 8. 文本分块器

代码位于 `src/research_agent/rag/chunker.py`。

默认配置：

```python
max_chars = 1200
overlap_chars = 200
```

### 8.1 分块原因

整篇长文档直接生成一个向量会造成粒度过粗、定位困难、无关内容过多和输入超限，因此必须切成较小片段。

### 8.2 处理过程

1. 将不同平台换行统一为 `\n`。
2. 优先按自然段落切分。
3. 尽量将多个短段落组合到一个 chunk。
4. 超长段落使用滑动窗口。
5. 相邻窗口保留重叠内容。

默认窗口类似：

```text
chunk 1：字符 0-1200
chunk 2：字符 1000-2200
chunk 3：字符 2000-3200
```

重叠可以减少答案恰好跨越边界时的信息损失。

## 9. Embedding 抽象

代码位于 `src/research_agent/rag/embeddings.py`。

### 9.1 EmbeddingProvider

```python
class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
```

索引器和检索器不需要知道向量来自本地算法还是远程 API。

### 9.2 HashEmbeddingProvider

本地教学向量器的处理过程：

```text
文本转小写
  ↓
切分词元
  ↓
补充字符二元组
  ↓
BLAKE2b 稳定哈希
  ↓
映射到固定维度
  ↓
根据哈希位决定正负
  ↓
L2 归一化
```

中文二元组示例：

```text
"工具调用" → "工具"、"具调"、"调用"
```

它属于 feature hashing，适合验证 RAG 数据流和词面匹配，不具备专业 embedding 模型的同义词、跨语言和抽象语义能力。

### 9.3 OpenAIEmbeddingProvider

远程 provider 调用兼容的 `/embeddings` 接口，并校验：

- 返回向量数量。
- index 顺序。
- 每个向量类型。
- 向量维度。
- 所有元素是否为数值。

## 10. 文档索引器

代码位于 `src/research_agent/rag/indexer.py`。

### 10.1 文件约束

允许 `.txt`、`.md`、`.rst`、`.csv`、`.json`、`.py`，单文件最大 2 MiB，必须位于 workspace 中并使用 UTF-8。

### 10.2 稳定 ID 和内容哈希

```python
document_id = sha256(source_uri)[:24]
content_hash = sha256(file_bytes)
```

URI 不变时 document ID 稳定。内容哈希与数据库相同则返回 `unchanged`，避免重复生成 embedding。

### 10.3 索引流程

```python
chunks = chunker.split(content)
vectors = embeddings.embed([chunk.content for chunk in chunks])
vector_store.replace_document(document, chunks, vectors)
```

chunk 和 vector 必须按索引一一对应。

## 11. SQLite 向量存储

代码位于 `src/research_agent/rag/vector_store.py`。

### 11.1 更新文档

更新时先删除旧 document，外键级联删除旧 chunks，再在同一事务中写入新 document 和 chunks。

### 11.2 余弦检索

当前实现从 SQLite 读取全部向量，在 Python 中计算：

```text
cosine(A, B) = (A · B) / (||A|| × ||B||)
```

结果按分数倒序排列，再应用最低分数和 top-k。

单条损坏向量会被跳过，不影响其他文档检索。

该实现适合小型教学库，复杂度接近 `O(chunk 数量 × 向量维度)`，不适合大规模向量数据。

## 12. Retriever

代码位于 `src/research_agent/rag/retriever.py`。

```text
查询文本
  ↓ 同一 EmbeddingProvider
查询向量
  ↓ SQLiteVectorStore.search()
RetrievalHit 列表
  ↓ to_sources()
EvidenceSource 列表
```

索引和检索必须使用相同 provider、模型和维度。`to_sources()` 是 RAG 系统与引用系统的连接点。

## 13. 三层记忆概览

| 类型 | 生命周期 | 存储 | 内容 |
| --- | --- | --- | --- |
| 短期记忆 | 单次 run | Python 内存 | 当前问题、工具结果、模型输出 |
| 会话记忆 | 多次 run | SQLite | 用户问题和最终回答 |
| 长期记忆 | 跨会话 | SQLite + embedding | 稳定偏好和显式记忆 |

## 14. 短期记忆

代码位于 `src/research_agent/memory/short_term.py`。

内部保存完整当前运行历史，但真正发送给 LLM 的是预算内 snapshot。

选择规则：

1. 始终保留 system。
2. 始终保留 pinned 当前研究问题。
3. 从最新消息向前选择。
4. 放不下时停止。
5. 如果裁剪，加入明确通知。

```text
[短期上下文已裁剪：省略较早的 6 条消息；请以当前证据为准。]
```

当前实现按字符数近似预算，不是真实 token 计数。

## 15. 会话记忆

代码位于 `src/research_agent/memory/session.py`。

会话记忆只保存用户问题和验证通过的最终回答，不保存内部工具 trace、协议错误和中间 JSON。

加载时按 message ID 倒序取最近记录，再反转恢复时间顺序。

旧回答中可能存在上一轮的 `[S1]`，但 S 编号是 run-local，因此载入时明确标记旧 S 编号在本轮无效。

## 16. 长期记忆

代码位于 `src/research_agent/memory/long_term.py`。

### 16.1 namespace

不同用户或项目应使用不同 namespace，避免记忆串用。

### 16.2 稳定 memory ID

```python
memory_id = sha256(namespace + "\n" + content)[:24]
```

相同 namespace 和内容会生成相同 ID，数据库使用 upsert 更新，不会无限插入重复项。

### 16.3 相关性召回

保存内容和查询都使用同一 embedding provider。召回时计算余弦相似度，过滤最低分数并返回 top-k。

长期记忆可能主观、过时或未验证，因此只作为用户上下文，不会转换成 EvidenceSource。

## 17. 工具统一接口

代码位于 `src/research_agent/tools/base.py`。

```python
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    def execute(self, arguments: object, context: ToolContext) -> ToolResponse:
        ...
```

`ToolExecution` 另外记录工具名、参数指纹、耗时和 ToolResponse。

## 18. 工具注册表与参数指纹

代码位于 `src/research_agent/tools/registry.py`。

参数先规范化：

```python
canonical = json.dumps(
    arguments,
    sort_keys=True,
    separators=(",", ":"),
)
```

再生成：

```python
fingerprint = sha256(tool_name + "\n" + canonical)
```

键顺序不同但语义相同的参数会得到相同指纹。

工具在线程池中执行，注册表统一处理未知工具、超时、异常、错误返回类型和耗时，并将所有失败归一化为 ToolResponse.error。

## 19. RAG 搜索工具

代码位于 `src/research_agent/tools/rag_search.py`。

它验证 query 和 top_k，调用 Retriever。无结果返回 empty；有结果返回标题、片段、相似度、locator 和 EvidenceSource。

## 20. 文件搜索工具

代码位于 `src/research_agent/tools/file_search.py`。

```text
rag_search  → 向量相似度，适合概念和语义
file_search → 精确关键词，适合名称和固定术语
```

安全边界包括：

- 目标路径必须位于 workspace。
- 每个实际文件再次 resolve，阻止符号链接逃逸。
- 只读取白名单扩展名。
- 单文件最多 512 KiB。
- 文件必须是 UTF-8。
- 限制结果数量。
- 每个命中保留行号。

## 21. 数据库查询工具

代码位于 `src/research_agent/tools/database_query.py`。

限制包括：

1. 数据库位于 workspace。
2. SQLite 使用 `mode=ro` 打开。
3. SQL 以 SELECT 或 WITH 开头。
4. 不允许多条语句。
5. 使用位置参数。
6. 最多返回 100 行。
7. progress handler 定期检查取消和 deadline。

它读取 `max_rows + 1` 行，用额外一行判断结果是否被截断。

## 22. 网络搜索工具

代码位于 `src/research_agent/tools/web_search.py`。

当前实现使用 MediaWiki 搜索 API，限制结果数、响应大小和超时，清理 HTML 摘要并构造公开文章 URL。

搜索摘要可以形成 EvidenceSource，但系统提示词要求对关键页面继续使用 browser_fetch 核实正文。

## 23. 网页抓取工具

代码位于 `src/research_agent/tools/browser_fetch.py` 和 `html_utils.py`。

### 23.1 URL 和 SSRF 基础防护

只允许 HTTP(S)，禁止 URL 用户名和密码。域名解析后的所有 IP 必须是 global 地址；重定向目标再次验证，因此拒绝 localhost、内网、link-local 和保留地址。

该防护不能替代生产环境的出站网络策略、DNS 重绑定防护和代理隔离。

### 23.2 内容约束

只接受 HTML、纯文本和 JSON，响应最多 2 MiB，提取文本最多 20000 字符。

HTMLTextExtractor 忽略 script、style、noscript 和 svg，并提取标题与正文。它不执行 JavaScript，因此不能处理完全依赖前端渲染的页面。

## 24. 受限 Python 代码工具

代码位于 `src/research_agent/tools/code_execution.py`。

默认 `ENABLE_CODE_EXECUTION=false`。

代码先使用 AST 检查，拒绝 import、属性访问、函数/类定义、lambda、with、try、raise、global、await、yield 和下划线名称。

函数调用只能使用白名单，例如 sum、len、range、sorted、sqrt、log 和 print。

通过检查后在 `python -I` 子进程中执行。子进程清空普通 builtins，只注入白名单函数，同时限制输出、CPU、文件大小、地址空间和墙钟时间。

这只是教学用风险降低措施，不是经过安全证明的多租户沙箱。

## 25. 记忆工具

代码位于 `src/research_agent/tools/memory_tools.py`。

`recall_memory` 按当前 namespace 召回长期记忆，但不返回 EvidenceSource。

`save_memory` 要求 content 和 reason。系统提示词规定只有用户明确要求记住稳定偏好或事实时才能调用。

## 26. 证据账本

代码位于 `src/research_agent/evidence/ledger.py`。

工具来源按出现顺序获得 S1、S2、S3。编号只在当前 run 中有效。

去重键为：

```python
(source.uri, source.locator)
```

同一来源后续获得更长 snippet 时会更新证据内容，但保留原编号。

## 27. 引用校验

代码位于 `src/research_agent/evidence/validator.py`。

最终输出示例：

```json
{
  "type": "final",
  "answer": "Stage 2 增加了 RAG。[S1]",
  "citations": ["S1"]
}
```

校验内容：

1. 最终答案非空。
2. citations 和正文 `[Sx]` 中的编号都必须存在。
3. 已经获得证据时不能省略 citations。
4. 正文标记集合必须与 citations 数组一致。

当前校验只能证明引用编号来自真实工具结果，不能证明某个来源片段确实支持对应结论。后者需要引用蕴含评测。

## 28. Agent 输出协议和系统提示词

协议位于 `src/research_agent/agent/protocol.py`。

工具调用：

```json
{
  "type": "tool_call",
  "tool_name": "rag_search",
  "arguments": {"query":"Stage 2 记忆机制"}
}
```

最终回答：

```json
{
  "type": "final",
  "answer": "Stage 2 使用三层记忆。[S1]",
  "citations": ["S1"]
}
```

相比 Stage 1，FinalDecision 多了 citations 字符串数组。

系统提示词位于 `agent/prompt.py`，规定优先本地 RAG、本地不足时网络搜索、关键页面继续抓取、空结果不能作为证据、不得重复调用、不得编造 URL、记忆不能作为事实来源。

## 29. Research Agent Loop

核心代码位于 `src/research_agent/agent/loop.py`。

### 29.1 初始化

```python
deadline = time.monotonic() + timeout_ms / 1000
ledger = EvidenceLedger()
short_term = ShortTermMemory(system_prompt, context_max_chars)
```

每次 run 都创建新的证据账本，所以 S 编号不会跨任务共享。

### 29.2 加载记忆和固定任务

Agent 加载最近会话消息和与任务相关的长期记忆，再将当前任务作为 pinned 消息加入短期上下文，并把用户问题写入会话数据库。

### 29.3 模型循环

每一步生成预算内 snapshot，调用 LLM，保存原始输出，再解析工具调用或最终答案。LLM 和工具超时都取自身上限与 Agent 剩余总时间的较小值。

### 29.4 最终答案校验

FinalDecision 必须先通过 CitationValidator。只有校验成功，才保存 assistant 会话消息并返回 ResearchResult。

引用或协议错误会被作为新消息反馈给模型重新生成。

### 29.5 重复调用拦截

每次 run 记录工具名和规范化参数的指纹。完全相同的第二次调用不会再次执行真实工具，而是返回 `REPEATED_TOOL_CALL`。参数实质变化后仍允许重试。

### 29.6 工具结果和证据登记

工具执行后，sources 进入 EvidenceLedger，得到 S 编号。回填消息包含工具状态、摘要、错误码、数据和已注册来源。

工具结果被包裹为“不可信数据而非指令”，用于降低文件或网页 prompt injection 的影响。

### 29.7 最终结果

```python
ResearchResult(
    answer=...,
    sources=...,
    steps=...,
    session_id=...,
)
```

CLI 根据 sources 输出真实标题、locator 和 URI，模型不直接负责生成最终链接。

## 30. 完整研究任务示例

先索引：

```bash
research-agent index Plan.md stage-1-minimal-agent/docs
```

再提问：

```text
比较 Stage 1 和 Stage 2 的主要能力差异
```

### 第一步：上下文

```text
system: 研究协议、工具和引用规则
user: 旧会话历史（如有）
user: 相关长期记忆（如有）
user: 当前研究问题（pinned）
```

### 第二步：模型调用 RAG

```json
{
  "type": "tool_call",
  "tool_name": "rag_search",
  "arguments": {
    "query": "Stage 1 Stage 2 能力差异",
    "top_k": 5
  }
}
```

### 第三步：查询向量检索

```text
查询文本 → query embedding → SQLite chunks
        → 余弦相似度 → 最低分过滤 → top-k
```

### 第四步：证据登记

假设命中 Stage 1 和 Stage 2 两个片段，账本分配 S1 和 S2。

### 第五步：结果回填

模型收到每个来源的 source_id、标题、URI、snippet 和 locator。

### 第六步：可能继续精确搜索

模型可调用 file_search 或 web_search/browser_fetch，新的来源继续获得 S3、S4。

### 第七步：最终输出

```json
{
  "type": "final",
  "answer": "Stage 1 实现最小工具循环。[S1] Stage 2 增加了 RAG、三层记忆和引用校验。[S2][S3]",
  "citations": ["S1", "S2", "S3"]
}
```

### 第八步：验证和输出

程序验证所有编号存在且正文与 citations 一致，然后输出回答及账本中的真实 URI。

## 31. 错误分层

错误位于 `src/research_agent/errors.py`。

| 错误 | 含义 | 处理方式 |
| --- | --- | --- |
| `ConfigError` | 环境变量错误 | 终止 |
| `LLMError` | LLM 网络或响应错误 | 终止 |
| `EmbeddingError` | 向量服务错误 | 终止索引或召回 |
| `ProtocolError` | 模型 JSON 错误 | 反馈模型修正 |
| `ToolError` | 工具取消或执行错误 | 转换为 error 结果 |
| `StorageError` | SQLite 或索引错误 | 终止对应操作 |
| `CitationError` | 最终引用不合法 | 反馈模型重写 |
| `AgentLimitError` | 超步骤或总超时 | 终止 |

恢复策略：

```text
格式错误 → 模型重写
引用错误 → 模型重写
工具错误 → 作为观察交给模型
工具空结果 → 修改查询或来源
配置/存储/LLM 错误 → 终止
无限循环 → 最大步骤和总时限终止
```

## 32. 当前边界

- 本地哈希向量主要匹配词面，不是真正语义 embedding。
- 分块和上下文预算使用字符数，不是模型 token。
- SQLite 向量检索执行全表扫描。
- 更换 embedding provider 或维度后需要重建索引。
- 网络搜索当前主要面向 MediaWiki。
- HTML 抓取不执行 JavaScript。
- SSRF 防护不是完整生产网络隔离。
- 受限 Python 工具不是通用安全沙箱。
- ThreadPoolExecutor 超时仍是协作式取消。
- 引用校验不能证明来源真正支持句子。
- 长期记忆可能过期，因此不会被当作证据。
- prompt injection 只有基础数据边界，没有动态安全评测。
- 系统不会自动索引文件，必须先执行 index。
- 尚未实现 reranker、混合检索和查询改写。

## 33. 推荐源码阅读顺序

1. `models.py`：工具三态结果和证据模型。
2. `storage/database.py`：数据库表结构。
3. `rag/chunker.py`：文档分块。
4. `rag/embeddings.py`：文本转向量。
5. `rag/indexer.py`：构建索引。
6. `rag/vector_store.py`：余弦检索。
7. `memory/short_term.py`：上下文预算。
8. `memory/session.py`：会话恢复。
9. `memory/long_term.py`：长期记忆召回。
10. `tools/registry.py`：工具执行和超时。
11. `evidence/ledger.py`：来源编号。
12. `evidence/validator.py`：引用校验。
13. `agent/protocol.py` 和 `prompt.py`：模型协议。
14. `agent/loop.py`：完整研究循环。
15. `main.py`：CLI 组件组装。

Stage 2 最终可以压缩为：

```python
先把资料分块、向量化并存入 SQLite

while 没有合格答案:
    加载预算内短期上下文
    模型决策 = 调用_LLM()

    if 模型要求工具:
        阻止完全重复调用
        工具结果 = 执行工具()
        来源编号 = 证据账本.register(工具结果.sources)
        短期上下文.add(工具结果和来源编号)
        continue

    if 模型返回最终答案:
        校验正文引用和 citations
        保存会话回答
        return 回答和真实来源链接
```
