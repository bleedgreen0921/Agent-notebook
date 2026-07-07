# OpenAI File Search 工具文档分析总结

来源页面：https://developers.openai.com/api/docs/guides/tools-file-search  
相关参考：https://developers.openai.com/api/docs/guides/retrieval  
整理日期：2026-07-07

## 1. 一句话结论

File search 是 OpenAI Responses API 中的托管检索工具。它让模型在生成回答前，从你上传到 vector store 的文件知识库中检索相关信息，并把检索结果作为上下文用于回答。你不需要自己实现向量化、分块、索引和工具执行流程，OpenAI 会托管这些检索步骤。

## 2. 适用场景

适合：

- 面向私有文档、FAQ、产品手册、政策文件、知识库的问答。
- 希望模型回答时引用上传文件，而不是只依赖模型预训练知识。
- 不想自行维护 embedding、chunking、向量数据库和 reranking 管线的应用。
- 对接 Responses API 的 agent 或客服、内部助手、文档搜索类工具。

不适合或需要谨慎：

- 需要完全自定义检索算法、索引策略、排序模型或向量数据库部署的场景。
- 需要强结构化查询、复杂权限模型、行级安全控制或事务型数据库查询的场景。
- 对成本、延迟、召回质量有严格指标时，仍需做评测和参数调优。

## 3. 核心概念

### File search

`file_search` 是 Responses API 的工具类型。模型可在需要时自动调用该工具，基于用户问题到指定的 `vector_store_ids` 中搜索文件内容。

### Vector store

Vector store 是可检索文件集合的容器。文件加入 vector store 后，会被自动处理为可搜索索引。Retrieval 指南说明，文件会被自动分块、嵌入并建立索引。

### File 与 vector_store.file

- `file`：通过 Files API 上传的原始文件对象。
- `vector_store`：可搜索文件集合。
- `vector_store.file`：文件加入 vector store 后的包装对象，可带 `attributes` 元数据，用于过滤。

## 4. 基本使用流程

### 4.1 上传文件

文档示例先通过 Files API 上传文件。页面示例中使用的上传目的为 `purpose="assistants"`。

### 4.2 创建 vector store

创建一个 vector store 作为知识库容器，例如 `knowledge_base` 或 `Support FAQ`。

### 4.3 将文件加入 vector store

把上传得到的 `file_id` 关联到 `vector_store_id`。文档也展示了 `upload_and_poll` 这类便捷流程，可在上传后等待处理完成。

### 4.4 检查处理状态

文件加入 vector store 后需要等待处理完成。只有状态为 `completed` 后，才适合作为检索源使用。

### 4.5 在 Responses API 中启用工具

调用 `responses.create` 时，将 `file_search` 加到 `tools`，并传入要搜索的 `vector_store_ids`：

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    input="根据知识库回答用户问题",
    tools=[{
        "type": "file_search",
        "vector_store_ids": ["<vector_store_id>"]
    }]
)
```

截至本次整理时，官方页面示例使用 `gpt-5.5`。

## 5. 响应结构理解

当模型调用 File search 后，响应通常包含两类输出项：

- `file_search_call`：表示一次检索调用，包含调用 ID、状态、查询语句等信息。
- `message`：模型最终回答，回答内容中可能包含文件引用注解。

默认情况下，`file_search_call` 不返回完整搜索结果，只能在文本输出中看到文件引用注解。如果需要把检索结果也放入响应，应在创建 response 时加入：

```python
include=["file_search_call.results"]
```

这对调试召回质量、查看命中文档片段、做可观测性记录很有用。

## 6. 检索自定义能力

### 6.1 控制返回结果数量

`max_num_results` 用于限制从 vector store 中取回的结果数量。减少结果数通常可降低 token 用量和延迟，但可能牺牲回答质量或召回覆盖。

```python
tools=[{
    "type": "file_search",
    "vector_store_ids": ["<vector_store_id>"],
    "max_num_results": 2
}]
```

### 6.2 元数据过滤

可以基于文件属性过滤检索结果。File search 页面展示了在工具配置中使用 `filters`：

```python
tools=[{
    "type": "file_search",
    "vector_store_ids": ["<vector_store_id>"],
    "filters": {
        "type": "in",
        "key": "category",
        "value": ["blog", "announcement"]
    }
}]
```

Retrieval 指南进一步说明，过滤器支持比较操作和复合条件：

- 比较操作：`eq`、`ne`、`gt`、`gte`、`lt`、`lte`、`in`、`nin`
- 复合操作：`and`、`or`
- 可按属性如 `region`、`date`、`category` 过滤，也可按文件名属性过滤。

### 6.3 排序和相关性阈值

Retrieval 指南提到可通过 `ranking_options` 调整相关性质量，包括：

- `ranker`：如 `auto` 或指定 ranker。
- `score_threshold`：0.0 到 1.0，阈值越高越偏向高相关片段，但可能排除有用内容。
- `hybrid_search` 权重：在支持时可调节语义匹配和关键词匹配的权重。

## 7. 支持的文件类型

File search 页面列出支持多种文本、代码、办公文档和 PDF 类型，包括：

- 文本文档：`.txt`、`.md`、`.json`
- 代码文件：`.py`、`.js`、`.ts`、`.java`、`.go`、`.rb`、`.php`、`.c`、`.cpp`、`.cs`、`.css`、`.sh`、`.tex`
- 网页和文档：`.html`、`.pdf`、`.doc`、`.docx`、`.pptx`

对于 `text/` MIME 类型，编码必须是 `utf-8`、`utf-16` 或 `ascii`。

## 8. 速率和成本注意点

页面的 usage notes 显示 File search 与 Responses、Chat Completions、Assistants 等 API 相关，并列出按 tier 区分的 RPM 限制：

- Tier 1：100 RPM
- Tier 2 和 Tier 3：500 RPM
- Tier 4 和 Tier 5：1000 RPM

Retrieval 指南说明，vector store 会根据所有 vector store 中解析后 chunk 及 embedding 所占存储计费。页面还提示可通过过期策略控制成本。

## 9. 工程落地建议

### 9.1 数据建库

- 按业务边界拆分 vector store，例如产品文档、客服 FAQ、法务政策分开存储。
- 上传文件时设计稳定的 `attributes`，例如 `category`、`region`、`language`、`version`、`effective_date`。
- 对频繁变更的文件建立同步机制：新增、更新、删除都要同步到 vector store。

### 9.2 查询质量

- 默认先记录 `file_search_call`，并在调试环境打开 `include=["file_search_call.results"]`。
- 针对典型问题集做评测，比较不同 `max_num_results`、过滤条件和排序阈值下的准确率与延迟。
- 如果答案经常引用旧文档，应优先补充日期、版本、状态等 metadata，然后使用过滤器限制范围。

### 9.3 用户回答

- 在面向用户的答案中保留文件引用信息，便于追踪来源。
- 如果检索结果不足，应让模型明确说明知识库中未找到足够依据，而不是强行回答。
- 对高风险领域，建议将引用、命中文档、回答置信度和人工复核流程一起设计。

### 9.4 成本和延迟

- `max_num_results` 不是越大越好，应在召回质量、token 消耗和延迟之间权衡。
- 对小型知识库可先用默认配置；对大型知识库应尽早引入 metadata 过滤。
- 定期清理废弃 vector store 和过期文件，避免长期存储费用累积。

## 10. 常见风险点

- 只上传文件但未加入 vector store，模型无法通过 `file_search` 检索。
- 文件还未处理到 `completed` 状态就开始查询，可能导致召回为空或不稳定。
- 未设计 metadata，后续很难做版本、地区、语言、权限等过滤。
- 默认不返回完整 search results，排查问题时容易误以为工具没有检索。
- `score_threshold` 设置过高可能导致相关片段被过滤掉；设置过低可能引入噪声。
- 多个 vector store 混用时，需要明确当前问题应搜索哪些知识库。

## 11. 推荐最小实现骨架

1. 创建 vector store。
2. 上传文件并加入 vector store。
3. 轮询直到文件状态为 `completed`。
4. 调用 Responses API，传入 `file_search` 工具和 `vector_store_ids`。
5. 在调试环境加入 `include=["file_search_call.results"]`。
6. 记录问题、检索结果、最终回答和引用文件。
7. 基于评测结果调整 `max_num_results`、metadata filters 和 ranking 设置。

## 12. 总体评价

File search 是一个低运维成本的托管 RAG 入口。它把文件上传、自动分块、embedding、索引、检索调用和回答引用整合到了 OpenAI API 中，适合快速把私有知识库接入模型。

它的关键设计点不在于“能不能检索”，而在于数据组织和调优：vector store 怎么拆、文件 metadata 怎么设计、查询时如何过滤、返回多少结果、如何观测召回质量。对生产系统来说，建议从小规模知识库开始，先建立评测集和日志，再逐步调优检索参数与元数据策略。
