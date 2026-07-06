# 小目标 2：接入搜索、数据库、文件、浏览器和代码工具

## 目标

通过统一 Tool Protocol 接入不同 I/O 能力，同时确保模型参数始终被当作不可信输入。

## 统一工具协议

- `name`：稳定工具名。
- `description`：帮助模型选择工具。
- `input_schema`：参数结构说明，不替代运行时校验。
- `execute(arguments, context)`：返回 `ToolResponse`。
- `ToolResponse.status` 明确区分 `success`、`empty`、`error`。

`ToolRegistry` 负责重名检查、参数指纹、线程池执行、超时、异常转换和耗时记录。

## 各工具实施计划

### `web_search`

- 使用 MediaWiki 搜索 API，无需额外 SDK。
- 限制结果数量、响应大小和超时。
- 清理 HTML 摘要并构造公开文章链接。

### `database_query`

- 数据库路径必须位于工作区。
- SQLite 使用 `mode=ro` 打开。
- 仅接受单条 `SELECT` 或 `WITH`。
- 使用位置参数，最多返回 100 行。

### `file_search`

- 搜索路径必须位于工作区真实路径内。
- 只处理白名单文本扩展名和 UTF-8。
- 限制单文件大小、结果数，逐次检查取消事件。

### `browser_fetch`

- 只允许 HTTP(S)，禁止 URL 用户名和密码。
- DNS 解析后拒绝非全局 IP，重定向目标再次校验。
- 限制 MIME、响应大小、正文字符数和超时。
- HTMLParser 忽略 script/style 并提取标题与正文。

这属于基础 SSRF 防护；DNS 重绑定、系统代理和复杂网络边界仍需要生产环境的出站网络策略配合。

### `python_code`

- 默认关闭，必须显式设置 `ENABLE_CODE_EXECUTION=true`。
- AST 拒绝 import、属性访问、函数/类定义及危险语法。
- 只允许调用白名单纯计算函数。
- 使用 `python -I` 子进程、受限 builtins、墙钟超时和 Unix 资源上限。

## 代码执行边界

受限 Python 工具是教学用的风险降低措施，不是经过安全证明的多租户沙箱。Python 解释器不是安全边界；生产系统应使用容器、虚拟机或专用沙箱，并实施网络隔离、文件系统隔离和系统调用限制。

## 对应代码

- `tools/base.py`、`tools/registry.py`
- `tools/web_search.py`
- `tools/database_query.py`
- `tools/file_search.py`
- `tools/browser_fetch.py`、`tools/html_utils.py`
- `tools/code_execution.py`

## 验收标准

- [x] 所有工具使用相同输入输出协议。
- [x] 数据库查询是只读且有行数上限。
- [x] 文件和数据库路径不能越过工作区。
- [x] 浏览器拒绝本机、内网和保留地址。
- [x] 代码执行默认关闭且有多层限制。
- [ ] 在可运行环境中完成动态 SSRF 和沙箱逃逸测试。
