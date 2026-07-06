Stage 1：构建最小 Agent Loop

实施记录：[Stage 1：最小 Agent Loop（Python）](./stage-1-minimal-agent/README.md)

当前状态：Python 实施计划与代码已完成；按环境约束未安装、未运行。

会用一个 LLM API 完成普通对话。

会让模型输出结构化 JSON。

会定义一个工具函数，例如 search、calculator、read_file。

会解析模型的 tool call / function call。

会执行工具，并把工具结果喂回模型。

会给 agent loop 加最大步数、超时和错误处理。

产出：一个最小 agent，可以选择工具、执行工具、返回最终答案。



Stage 2：学习工具调用、RAG与记忆

实施记录：[Stage 2：RAG 与记忆研究助手（Python）](./stage-2-rag-memory-agent/README.md)

当前状态：Python 实施计划与代码已完成；按环境约束未安装、未运行。

会做检索增强生成：chunk、embed、retrieve、answer with citations。

会把搜索、数据库、文件、浏览器、代码执行接成工具。

会区分短期上下文、会话记忆、长期记忆。

会处理工具失败、空结果、重复调用、幻觉引用。

会让 agent 在回答里给出来源或证据。

产出：一个资料研究助手，输入主题后自动搜索、筛选、总结并输出引用链接。



Stage 3：深入研究一个现代 Agent Harness

读懂一个 agent harness的目录结构。

#*WE agent loop, tool registry, permission gate, session store, context compaction.

跑通它的最小示例，并加一个你自己的工具。

观察一次完整trace，解释每一步为什么发生。

把同一个任务分别用

「裸agent loop」和「harness」实现，对比差异。

产出：一个可调试的 agent harness demo，包含 README、运行步骤、示例输入输出和失败记录。


Stage 4：多 Agent 是协调问题，不是魔法

理解 planner / executor / reviewer/ critic / router 等常见角色。

学会用 supervisor 或 graph 管理多 agent，而不是让 agent 随便聊天。

会定义每个 agent 的职责边界、输入输出 schema、停止条件。

会处理循环、争论、任务漂移、上下文膨胀。

会判断什么时候单 agent 更好。

产出：一个小型多 agent 系统，例如 research write review revise。


Stage 5：学习 Skills、协议与能力打包

理解 Skill 和Tool的区别：tool 是可调用接口，skill 是可复用流程知识。

理解 Skill和 Prompt 的区别：prompt 通常是一次性指令，skill 是可发现、可版本化、可分发的能力包。

理解 Skill和MCP的区别：MCP 接入外部工具/数据源，skill 告诉 agent 如何完成一类任务。

阅读 Claude Code Skills 的文件结构和触发机制。

阅读 OpenClaw Skills 的加载、作用域和安全边界。

写一个最小 SKILL.md，包含 name、description、何时使用、步骤、验收标准。

给skill 加一个脚本或模板文件，并说明 agent什么时候才需要加载。

给 skill写一个 smoke test，验证它是否真的提升任务成功率。


产出：一个可复用 skill，例如 code-review、research-report、 migration-helper、pdf-extraction 或 release-notewriter.


Stage 6：浏览器与 Computer-Use Agent

理解 browser agent 和普通 APl tool 的区别。

会用 Playwright 或 browser-use 做网页观察和点击。

会给浏览器操作加安全限制：不登录敏感账号、不越权、不绕过平台规则。

会处理页面变化、弹窗、加载失败、元素定位失败。

会记录截图、DOM、动作日志，方便复盘。

产出：一个只操作公开网页的 browser agent，

例如打开网页、提取信息、生成摘要。


Stage 7：评测、可观测性与安全

为 agent 准备固定测试集，而不是只看 demo。

记录成功率、失败原因、工具调用次数、成本、延迟。

会看trace，知道失败发生在 prompt、工具、检索、模型还是状态管理。

给危险工具加人工确认，例如发邮件、删文件、付款、发布内容。

了解 prompt injection、data exfiltration、tool abuse 等风险。

会用回归测试防止 prompt 或工具改动后能力退化。


Stage 8： 交付一个真正的 Agent

有明确用户、明确任务、明确成功标准。

有日志、trace、错误重试、超时、成本上限。

有权限边界和人工确认机制。

有部署方式：CLI、Web app、Slack bot、GitHub Action 或后台任务。

有 README：怎么运行、怎么配置key、怎么扩展工具、有哪些限制。

产出：一个别人能 clone 下来跑的 agent 项目。
