# 小目标 1：检索增强生成（RAG）

## 目标

完成 `chunk → embed → store → retrieve → answer with citations` 全链路，并让每个检索片段保留可追溯来源。

## 实施计划

### 1. 文档表示

- `TextDocument` 保存文档 ID、标题、URI、正文和内容哈希。
- 文档 ID 根据来源 URI 稳定生成。
- SHA-256 内容哈希用于判断是否需要重建索引。

### 2. Chunk

- 统一换行并忽略空段落。
- 优先按段落组合，超长段落使用滑动字符窗口。
- 默认最大 1200 字符，重叠 200 字符。
- 每块保存近似字符范围 locator。

### 3. Embed

- `EmbeddingProvider` Protocol 隔离具体向量服务。
- 默认哈希向量使用稳定 BLAKE2b 投影和 L2 归一化。
- 对中文无空格文本增加字符二元组。
- 可选 OpenAI-compatible `/embeddings`，验证数量、维度和元素类型。

### 4. Store

- SQLite `documents` 保存文档级元数据。
- `rag_chunks` 保存文本块、JSON 向量和定位信息。
- 更新文档在一个事务中删除旧块、写入新块。

### 5. Retrieve

- 查询使用同一 provider 向量化。
- 教学实现从 SQLite 读取向量并计算余弦相似度。
- 应用最低分数、top-k 排序。
- 命中转换为 `EvidenceSource`，传递 URI、标题、片段和 locator。

### 6. Answer

- `rag_search` 将命中片段及来源交给 Agent。
- 证据账本为来源分配 `[Sx]`。
- 引用校验通过后才输出回答和链接。

## 对应代码

- `rag/models.py`
- `rag/chunker.py`
- `rag/embeddings.py`
- `rag/vector_store.py`
- `rag/indexer.py`
- `rag/retriever.py`
- `tools/rag_search.py`

## 已知取舍

- 字符数不是 token 数；Stage 2 用确定、易读的方法演示分块。
- SQLite 全表余弦计算适合小型教学数据，不适合百万级向量。
- 本地哈希向量主要匹配词面，不具备专业 embedding 的语义质量。
- 切换 provider 或向量维度后必须重建索引。

## 验收标准

- [x] 文档内容未变化时不会重复索引。
- [x] 每个文本块保留原始 URI 和定位信息。
- [x] embedding provider 可替换。
- [x] 检索具备 top-k 和最低分数。
- [x] RAG 命中可以进入证据账本。
- [ ] 在可运行环境中建立固定语料召回率测试。
