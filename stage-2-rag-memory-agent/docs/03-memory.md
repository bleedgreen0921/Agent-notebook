# 小目标 3：区分短期上下文、会话记忆和长期记忆

## 概念边界

| 类型 | 生命周期 | 存储 | 内容 | 用途 |
| --- | --- | --- | --- | --- |
| 短期上下文 | 单次 Agent run | 内存 | 系统提示、当前任务、工具观察 | 当前推理 |
| 会话记忆 | 多次 run，同 session | SQLite | 用户问题、最终回答 | 延续对话 |
| 长期记忆 | 跨 session | SQLite + embedding | 稳定偏好、用户明确要求记住的事实 | 个性化召回 |

## 实施计划

### 短期上下文

- `ShortTermMemory` 始终保留系统提示词和当前研究问题。
- 新消息顺序写入内存。
- `snapshot()` 从最新消息向前选择，控制总字符预算。
- 裁剪时加入明确通知，避免模型误以为看到了全部历史。

### 会话记忆

- 按 `session_id` 保存 user/assistant 消息。
- 只持久化用户问题和验证通过的最终回答，不保存内部工具 trace。
- 新任务加载最近 10 条，并声明旧的 `[Sx]` 编号在本轮无效。

### 长期记忆

- 按 `namespace` 隔离不同用户或项目。
- 内容哈希形成稳定 memory ID，重复保存执行 upsert。
- 保存正文、metadata、embedding 和时间。
- 当前任务向量与同 namespace 记忆计算余弦相似度。
- CLI `remember` 支持显式写入；Agent 只有在用户明确要求时才应调用 `save_memory`。

## 信任边界

长期记忆可能过期或由用户主观提供，因此只能作为上下文，不能注册到证据账本，也不能产生 `[Sx]` 事实引用。

## 对应代码

- `memory/short_term.py`
- `memory/session.py`
- `memory/long_term.py`
- `tools/memory_tools.py`
- `storage/database.py`

## 验收标准

- [x] 三种记忆有独立类和存储策略。
- [x] 会话通过 session ID 隔离。
- [x] 长期记忆通过 namespace 隔离并支持语义召回。
- [x] 短期上下文有明确预算。
- [x] 记忆不会被当作外部证据。
- [ ] 在可运行环境中测试跨进程恢复和 namespace 隔离。
