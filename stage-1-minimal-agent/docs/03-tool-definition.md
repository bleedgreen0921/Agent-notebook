# 小目标 3：定义工具函数（Python）

## 目标

让不同 Python 能力通过统一接口注册、描述和执行。模型只能看到工具元数据，不能访问 Python 函数对象。

## 工具接口

`Tool` Protocol 约定四部分：

- `name`：稳定的机器可读名称。
- `description`：说明工具用途。
- `input_schema`：指导模型生成参数的 JSON Schema。
- `execute(arguments, context)`：校验并执行工具。

`ToolContext` 提供工作区根目录、取消事件和单次截止时间。

## 实施计划

1. 定义 `Tool`、`ToolContext` 和 `ToolExecutionResult`。
2. 用字典保存已注册工具。
3. 注册时校验名称并拒绝重名。
4. `describe()` 深拷贝元数据，避免外部修改工具定义。
5. 用线程池执行工具，通过 `future.result(timeout=...)` 限时等待。
6. 统一捕获工具异常，返回成功状态、输出、错误和耗时。
7. 实现安全计算器：手写递归下降解析器，不使用 `eval()`。
8. 实现文件读取：解析真实路径，阻止 `..` 和符号链接逃逸，限制 100 KiB 与 UTF-8。

## 对应代码

- `src/minimal_agent/tools/base.py`
- `src/minimal_agent/tools/registry.py`
- `src/minimal_agent/tools/calculator.py`
- `src/minimal_agent/tools/read_file.py`

## 添加新工具

1. 新建一个类，提供 `name`、`description` 和 `input_schema`。
2. 实现 `execute(self, arguments, context)`。
3. 使用 `isinstance()` 验证外部参数，不能只依赖 Schema。
4. 在耗时步骤前后调用 `context.raise_if_cancelled()`。
5. 返回能被 `json.dumps()` 序列化的数据。
6. 在 `main.py` 中创建并注册该工具。

## 安全边界

- 计算器不使用 `eval()` 或 `exec()`，表达式不能执行 Python 代码。
- 文件工具使用 `Path.resolve()` 和 `relative_to()` 阻止工作区逃逸。
- 文件读取前检查大小，实际读取时仍限制最大字节数，降低竞态风险。
- Python 线程无法安全地被外部强制终止，因此工具必须配合取消事件。

## 验收标准

- [x] 所有工具遵守统一 Protocol。
- [x] 非法、重复和未知工具名均有确定结果。
- [x] 计算器没有任意 Python 代码执行能力。
- [x] 文件读取不能越过工作区并拒绝非 UTF-8 文件。
- [x] 成功和失败都产生结构化执行结果。
- [ ] 在可运行环境中补充工具单元测试。
