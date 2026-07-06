# Stage 2 总体实施计划

## 阶段目标

实现一个 Python 资料研究助手：输入主题后，能够检索本地资料与公开网络，筛选证据，结合会话和长期记忆生成带引用回答，并对常见 Agent 失败模式做确定性处理。

## 技术选择

- Python 3.11+，标准库实现。
- `urllib.request`：LLM、embedding、搜索和网页 HTTP 请求。
- `sqlite3`：RAG 索引、会话消息和长期记忆持久化。
- `dataclass` 与 `Protocol`：数据模型和可替换接口。
- `ThreadPoolExecutor`：工具限时等待。
- `hashlib` 本地哈希向量：默认无外部 embedding 依赖。
- 自定义 JSON 决策协议：显式展示 Agent 控制流和引用校验。

## 实施顺序

1. 建立配置、错误、共享模型与 SQLite schema。
2. 实现 chunk、两种 embedding、向量存储、索引器和 retriever。
3. 建立统一工具协议和执行注册表。
4. 实现本地、数据库、网络、浏览器、代码与记忆工具。
5. 实现短期、会话、长期三层记忆。
6. 实现证据账本、引用验证和研究 Agent Loop。
7. 提供 `index`、`ask`、`remember` CLI。

## 模块依赖

```text
config / models / errors
       ↓
storage/database
  ├── rag ──> rag_search
  ├── session memory
  └── long-term memory ──> memory tools

independent tools ──┐
evidence ledger ────┼──> ResearchAgent Loop ──> CLI
LLM client ─────────┘
```

## 验收矩阵

| 场景 | 预期行为 |
| --- | --- |
| 索引新文件 | 分块、向量化并持久化来源元数据 |
| 再次索引未变文件 | 根据 SHA-256 跳过 |
| 本地检索命中 | 返回片段、分数、URI 和定位信息 |
| 外部研究 | 搜索结果提供链接，关键页面可继续抓取 |
| 工具失败 | 形成 `error` 结果并交回模型 |
| 工具无结果 | 形成独立 `empty` 状态，不作为证据 |
| 完全相同的工具调用 | 第二次被阻止并返回 `REPEATED_TOOL_CALL` |
| 会话继续 | 最近问题与回答按 session 恢复 |
| 长期记忆 | 按 namespace 保存并通过 embedding 召回 |
| 引用不存在 | 最终答案被拒绝并要求模型重写 |
| 有证据无引用 | 最终答案被拒绝 |
| 合法回答 | 输出正文 `[Sx]` 和对应来源链接 |

## 静态完成标准

- 五个小目标均有独立文档、对应 Python 模块和验收标准。
- 所有核心流程、安全边界、失败行为有中文注释。
- 工具参数和外部 JSON 进行运行时校验。
- 网络、文件、数据库、代码工具有明确权限与资源上限。
- 记忆与证据概念分离，长期记忆不能产生事实引用。
- 当前环境不运行 Python，不调用任何外部服务。
