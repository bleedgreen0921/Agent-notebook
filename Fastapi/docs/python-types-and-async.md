# FastAPI 中的 Python 类型提示与 async 并发

来源页面：

- <https://fastapi.tiangolo.com/zh/python-types/>
- <https://fastapi.tiangolo.com/zh/async/>

整理日期：2026-07-08

本文基于 FastAPI 官方中文文档中 “Python 类型提示” 与 “并发和 async / await” 两个页面整理，重点说明类型提示在 FastAPI 中如何驱动参数解析、数据校验、编辑器提示和接口文档生成，以及 `async def`、普通 `def`、并发、并行在 FastAPI 应用中的实际使用边界。

## 1. Python 类型提示概览

Python 是动态类型语言，变量本身不需要提前声明类型。但从 Python 3.5 开始，Python 支持在函数参数、返回值和变量上写类型提示。类型提示不会把 Python 变成静态类型语言，也不会在普通 Python 运行时强制检查所有类型，它的核心价值是给编辑器、类型检查器、框架和人类读者提供结构化信息。

FastAPI 深度依赖类型提示。你在路径函数、查询参数、请求体模型、依赖函数和响应模型中写下的类型，会被 FastAPI 用来完成：

- 请求参数提取。
- 字符串到目标类型的转换。
- 数据校验。
- 自动错误响应。
- OpenAPI Schema 生成。
- Swagger UI / ReDoc 文档生成。
- 编辑器自动补全和静态分析。

一个最小示例：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None) -> dict[str, int | str | None]:
    return {"item_id": item_id, "q": q}
```

这里的 `item_id: int` 不只是给编辑器看的。FastAPI 会从路径中读取 `item_id`，尝试把它转换为整数。如果请求 `/items/abc`，转换失败，FastAPI 会自动返回 422 校验错误。

## 2. 基础类型提示语法

### 2.1 函数参数类型

类型提示写在参数名后面，用冒号分隔：

```python
def get_full_name(first_name: str, last_name: str):
    return first_name.title() + " " + last_name.title()
```

`first_name: str` 和 `last_name: str` 表示这两个参数预期是字符串。编辑器可以据此提供 `.title()`、`.upper()`、`.strip()` 等字符串方法补全。

### 2.2 函数返回值类型

返回值类型写在参数列表后、冒号前，用 `->` 表示：

```python
def get_name_with_age(name: str, age: int) -> str:
    return f"{name} is {age} years old"
```

返回类型对 FastAPI 也很有帮助，但在接口响应上，更常见的是用 `response_model` 或 Pydantic 模型来明确响应结构。

```python
from pydantic import BaseModel
from fastapi import FastAPI


class UserOut(BaseModel):
    id: int
    name: str


app = FastAPI()


@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int) -> UserOut:
    return UserOut(id=user_id, name="Alice")
```

### 2.3 变量类型提示

变量也可以添加类型提示：

```python
name: str = "Alice"
age: int = 20
price: float = 9.99
is_active: bool = True
```

变量类型提示主要服务于编辑器和类型检查器。FastAPI 中更常见的是在函数参数和 Pydantic 模型字段上使用。

## 3. 常见内置类型

FastAPI 能识别并转换许多常见 Python 类型，例如：

```python
from datetime import date, datetime
from uuid import UUID

from fastapi import FastAPI

app = FastAPI()


@app.get("/orders/{order_id}")
async def read_order(
    order_id: UUID,
    created_after: date | None = None,
    include_deleted: bool = False,
):
    return {
        "order_id": order_id,
        "created_after": created_after,
        "include_deleted": include_deleted,
    }
```

请求示例：

```text
GET /orders/8f5f7a15-0d39-447f-9b4e-d2d91c36b08d?created_after=2026-01-01&include_deleted=true
```

FastAPI 会把：

- `order_id` 转成 `UUID`。
- `created_after` 转成 `date`。
- `include_deleted` 转成 `bool`。

如果格式不合法，FastAPI 会返回包含错误位置、错误原因和预期类型的 422 响应。

## 4. 泛型类型：list、tuple、set、dict

### 4.1 Python 3.9+ 推荐写法

Python 3.9 之后，可以直接使用内置集合类型作为泛型：

```python
tags: list[str] = ["python", "fastapi"]
coordinates: tuple[float, float] = (116.4, 39.9)
unique_ids: set[int] = {1, 2, 3}
prices: dict[str, float] = {"apple": 3.5, "banana": 2.8}
```

在 FastAPI 和 Pydantic 模型中也一样：

```python
from pydantic import BaseModel


class Product(BaseModel):
    name: str
    tags: list[str]
    attributes: dict[str, str]
```

### 4.2 Python 3.8 兼容写法

如果项目仍在使用 Python 3.8，需要从 `typing` 导入对应类型：

```python
from typing import Dict, List, Set, Tuple

tags: List[str] = ["python", "fastapi"]
coordinates: Tuple[float, float] = (116.4, 39.9)
unique_ids: Set[int] = {1, 2, 3}
prices: Dict[str, float] = {"apple": 3.5}
```

FastAPI 官方文档会同时展示不同 Python 版本下的写法。实际项目中应根据项目 Python 版本统一风格。

## 5. Union、Optional 与 None

### 5.1 `str | None`

Python 3.10+ 推荐使用 `|` 表示联合类型：

```python
def normalize_query(q: str | None) -> str:
    if q is None:
        return ""
    return q.strip()
```

`str | None` 表示值可以是字符串，也可以是 `None`。

在 FastAPI 查询参数中：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/search")
async def search(q: str | None = None):
    return {"q": q}
```

这里有两个信息：

- `q: str | None` 表示类型允许 `None`。
- `= None` 表示这个查询参数不是必填项。

这两点不要混淆。类型允许为空，不一定代表请求参数可省略；默认值才决定参数是否必填。

### 5.2 Python 3.8/3.9 的 `Union` 和 `Optional`

Python 3.10 之前常见写法：

```python
from typing import Optional, Union


def normalize_query(q: Optional[str]) -> str:
    if q is None:
        return ""
    return q.strip()


def parse_identifier(value: Union[int, str]) -> str:
    return str(value)
```

`Optional[str]` 等价于 `Union[str, None]`，也就是 Python 3.10+ 的 `str | None`。

### 5.3 必填但可为 None

这是 FastAPI 中很容易写错的点。

```python
from fastapi import Body, FastAPI
from typing import Annotated

app = FastAPI()


@app.post("/notes")
async def create_note(content: Annotated[str | None, Body()]):
    return {"content": content}
```

上例中没有给 `content` 默认值，所以请求体字段仍然是必填的，但字段值可以是 `null`。如果写成下面这样，字段就是可省略的：

```python
from fastapi import Body, FastAPI
from typing import Annotated

app = FastAPI()


@app.post("/notes")
async def create_note(content: Annotated[str | None, Body()] = None):
    return {"content": content}
```

## 6. 类作为类型

Python 的类也可以作为类型提示使用：

```python
class Person:
    def __init__(self, name: str):
        self.name = name


def greet(person: Person) -> str:
    return f"Hello {person.name}"
```

在 FastAPI 中，更常见的是用 Pydantic 的 `BaseModel` 类描述请求体和响应体。

```python
from pydantic import BaseModel
from fastapi import FastAPI


class User(BaseModel):
    username: str
    email: str
    age: int | None = None


app = FastAPI()


@app.post("/users")
async def create_user(user: User) -> User:
    return user
```

请求体示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "age": 20
}
```

FastAPI 会把 JSON 请求体解析为 `User` 模型，并校验：

- `username` 必须是字符串。
- `email` 必须是字符串。
- `age` 可以是整数，也可以省略。

## 7. Pydantic 模型与嵌套结构

FastAPI 使用 Pydantic 模型处理结构化数据。类型提示越准确，自动校验和文档就越准确。

```python
from pydantic import BaseModel, Field
from fastapi import FastAPI


class Address(BaseModel):
    city: str
    street: str
    zip_code: str = Field(pattern=r"^\d{6}$")


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str
    addresses: list[Address] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


app = FastAPI()


@app.post("/users")
async def create_user(user: UserCreate):
    return {
        "username": user.username,
        "address_count": len(user.addresses),
    }
```

这里体现了几个关键点：

- `addresses: list[Address]` 表示一个地址对象列表。
- `metadata: dict[str, str]` 表示字符串键和值的字典。
- `Field(default_factory=list)` 避免使用可变默认值。
- `Field(min_length=3, max_length=32)` 会体现在校验规则和 OpenAPI 文档中。

请求体示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "addresses": [
    {
      "city": "Beijing",
      "street": "Chang'an Avenue",
      "zip_code": "100000"
    }
  ],
  "metadata": {
    "source": "web"
  }
}
```

## 8. Annotated：类型与参数元数据分离

FastAPI 官方文档越来越推荐用 `typing.Annotated` 把“类型”与“参数说明、校验规则、依赖声明”等元数据放在一起。

```python
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(
    item_id: Annotated[int, Path(gt=0, description="Item ID")],
    q: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
):
    return {"item_id": item_id, "q": q}
```

`Annotated[int, Path(gt=0)]` 表示：

- 真正的 Python 类型是 `int`。
- FastAPI 额外读取 `Path(gt=0)` 作为路径参数校验和文档元数据。

这种写法比把 `Query()` 或 `Path()` 混在默认值里更清晰，尤其适合复杂参数。

## 9. FastAPI 如何利用类型提示

### 9.1 路径参数

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id}
```

请求 `/users/123` 时，`user_id` 是整数 `123`。请求 `/users/alice` 时，FastAPI 返回校验错误。

### 9.2 查询参数

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/items")
async def list_items(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(min_length=1)] = None,
):
    return {"limit": limit, "offset": offset, "q": q}
```

FastAPI 会自动识别这些是查询参数，并在文档里展示默认值、范围和是否必填。

### 9.3 请求体

```python
from pydantic import BaseModel
from fastapi import FastAPI


class ItemCreate(BaseModel):
    name: str
    price: float
    tags: list[str] = []


app = FastAPI()


@app.post("/items")
async def create_item(item: ItemCreate):
    return item
```

只要参数类型是 Pydantic 模型，FastAPI 通常会把它识别为请求体。

实际项目中建议避免 `tags: list[str] = []` 这种可变默认值，改用：

```python
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str
    price: float
    tags: list[str] = Field(default_factory=list)
```

### 9.4 响应模型

```python
from pydantic import BaseModel
from fastapi import FastAPI


class UserIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str


app = FastAPI()


@app.post("/users", response_model=UserOut)
async def create_user(user: UserIn):
    return user
```

`response_model=UserOut` 可以过滤响应中不应该暴露的字段。虽然函数返回了 `UserIn`，最终响应会按照 `UserOut` 输出，不包含 `password`。

### 9.5 依赖注入

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()


async def get_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing token")
    return authorization.removeprefix("Bearer ").strip()


@app.get("/me")
async def read_me(token: Annotated[str, Depends(get_token)]):
    return {"token": token}
```

依赖函数也可以使用类型提示。FastAPI 会对依赖函数的参数做同样的提取、转换和校验。

## 10. 类型提示实践建议

建议在 FastAPI 项目中遵守以下规则：

- 路径参数、查询参数、请求体、响应体、依赖返回值都尽量写清楚类型。
- Python 3.10+ 项目优先使用 `str | None`、`list[str]`、`dict[str, int]` 这类现代写法。
- Python 3.8 项目使用 `typing.Optional`、`typing.Union`、`typing.List`、`typing.Dict`。
- 对复杂请求体使用 Pydantic 模型，不要长期依赖裸 `dict`。
- 对字段约束使用 `Field()`，对接口参数约束使用 `Query()`、`Path()`、`Body()`、`Header()`、`Cookie()`。
- 新代码优先使用 `Annotated` 承载 FastAPI 参数元数据。
- 不要把“类型允许 None”和“参数可以省略”混为一谈。
- 避免可变默认值，使用 `Field(default_factory=list)` 或 `Field(default_factory=dict)`。
- 对外部接口的响应使用 `response_model` 或明确的返回模型，减少敏感字段泄漏风险。

## 11. async、await 与并发的核心概念

FastAPI 官方 async 文档的核心思想是：Web 服务大量时间都在等待外部 I/O，例如网络请求、数据库查询、文件系统、缓存服务、第三方 API。异步并发的价值在于，当当前请求正在等待 I/O 时，事件循环可以切换去处理其他请求，而不是让整个线程空等。

### 11.1 并发不是并行

并发关注“在同一段时间内处理多个任务”，任务之间可以在等待时切换。并行关注“在同一时刻真正执行多个任务”，通常依赖多个 CPU 核心或多个进程。

Web API 通常是 I/O 密集型，适合并发：

- 等数据库返回。
- 等 Redis 返回。
- 等 HTTP API 返回。
- 等对象存储返回。

机器学习推理、图片处理、视频转码、大量数学计算通常是 CPU 密集型，更需要并行：

- 多进程。
- 任务队列。
- 独立 worker。
- 专门的推理服务。
- GPU 或其他硬件加速。

FastAPI 可以同时受益于并发和并行。单个 ASGI worker 内部可以用 async 并发处理 I/O，部署层面也可以用多个 worker 或外部任务系统处理 CPU 密集任务。

### 11.2 `async def`

`async def` 定义异步函数：

```python
async def fetch_user(user_id: int) -> dict:
    ...
```

调用异步函数会得到一个协程对象。必须用 `await` 等待它真正执行完成：

```python
user = await fetch_user(1)
```

`await` 只能直接写在 `async def` 函数内部。

### 11.3 `await`

`await` 表示当前位置需要等待一个异步操作完成，但等待期间事件循环可以去运行其他可执行任务。

示例：

```python
import asyncio


async def slow_operation() -> str:
    await asyncio.sleep(1)
    return "done"


async def main():
    result = await slow_operation()
    print(result)
```

这里的 `asyncio.sleep(1)` 是非阻塞等待。它不会让事件循环卡死。

## 12. FastAPI 中何时使用 async def

如果路径操作函数内部需要调用异步库，并且你需要使用 `await`，就应该使用 `async def`。

典型异步库或异步接口包括：

- `httpx.AsyncClient`
- `asyncpg`
- SQLAlchemy async engine/session
- Motor，异步 MongoDB 客户端
- redis-py 的 async API
- aiofiles
- 其他返回 awaitable 的 SDK

示例：并发调用外部 HTTP 接口。

```python
import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.get("/github/users/{username}")
async def get_github_user(username: str):
    url = f"https://api.github.com/users/{username}"

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")

    response.raise_for_status()
    return response.json()
```

如果这里使用普通 `requests.get()` 放在 `async def` 中，就会阻塞事件循环，不利于并发。

## 13. FastAPI 中何时使用普通 def

如果你调用的是普通同步阻塞库，并且没有 `await`，可以使用普通 `def`。

```python
import requests
from fastapi import FastAPI

app = FastAPI()


@app.get("/sync-github/users/{username}")
def get_github_user_sync(username: str):
    response = requests.get(
        f"https://api.github.com/users/{username}",
        timeout=5,
    )
    response.raise_for_status()
    return response.json()
```

FastAPI 对普通 `def` 路径操作函数有特殊处理：它不会直接在事件循环里调用，而是会放到外部线程池中执行并等待结果。这样可以避免同步阻塞代码直接卡住事件循环。

因此，选择规则可以简化为：

- 需要 `await` 异步库时，用 `async def`。
- 使用同步阻塞库且暂时不能换异步版本时，用普通 `def`。
- 不确定第三方库是否异步时，看它的调用方式。如果文档要求 `await client.xxx()`，它是异步接口；如果直接 `client.xxx()` 返回结果，它通常是同步接口。

## 14. 不要在 async def 中直接执行阻塞操作

错误示例：

```python
import time
from fastapi import FastAPI

app = FastAPI()


@app.get("/bad-sleep")
async def bad_sleep():
    time.sleep(2)
    return {"ok": True}
```

`time.sleep(2)` 会阻塞当前线程。如果这个函数在事件循环线程中运行，整个事件循环都会被卡住，其他请求也会受影响。

正确示例：

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()


@app.get("/good-sleep")
async def good_sleep():
    await asyncio.sleep(2)
    return {"ok": True}
```

如果必须使用同步阻塞函数，可以把路径函数写成普通 `def`，让 FastAPI 放到线程池中执行：

```python
import time
from fastapi import FastAPI

app = FastAPI()


@app.get("/threadpool-sleep")
def threadpool_sleep():
    time.sleep(2)
    return {"ok": True}
```

## 15. 同时执行多个异步 I/O

异步的一个重要优势是可以在一个请求内并发等待多个 I/O。

```python
import asyncio
from typing import Any

import httpx
from fastapi import FastAPI

app = FastAPI()


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


@app.get("/dashboard")
async def dashboard():
    urls = [
        "https://api.example.com/profile",
        "https://api.example.com/orders",
        "https://api.example.com/messages",
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        profile, orders, messages = await asyncio.gather(
            *(fetch_json(client, url) for url in urls)
        )

    return {
        "profile": profile,
        "orders": orders,
        "messages": messages,
    }
```

如果这三个接口每个都要等待 300ms，串行请求大约需要 900ms。并发等待时，总耗时通常更接近最慢的那一次请求，而不是所有请求耗时之和。

生产环境中还应考虑：

- 超时。
- 重试。
- 熔断。
- 最大并发限制。
- 上游服务限流。
- 错误隔离。

带并发限制的示例：

```python
import asyncio
from typing import Any

import httpx


async def fetch_with_limit(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> dict[str, Any]:
    async with semaphore:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def fetch_many(urls: list[str]) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(timeout=5.0) as client:
        return await asyncio.gather(
            *(fetch_with_limit(client, semaphore, url) for url in urls)
        )
```

## 16. 依赖项中的 async def 与 def

FastAPI 的路径函数、依赖函数和子依赖函数都可以混用 `async def` 和普通 `def`。FastAPI 会根据函数类型选择合适的执行方式。

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


def get_settings() -> dict[str, str]:
    return {"region": "cn"}


async def get_current_user(
    settings: Annotated[dict[str, str], Depends(get_settings)],
) -> dict[str, str]:
    # 这里可以 await 异步数据库或异步认证服务
    return {"username": "alice", "region": settings["region"]}


@app.get("/account")
async def read_account(
    user: Annotated[dict[str, str], Depends(get_current_user)],
):
    return user
```

执行规则可以理解为：

- `async def` 依赖会在事件循环中被 await。
- 普通 `def` 依赖会在线程池中执行。
- 路径函数和依赖函数可以任意组合，FastAPI 会处理调用细节。

## 17. 普通工具函数不由 FastAPI 自动调度

FastAPI 只会自动处理路径操作函数、依赖函数、子依赖函数等由框架调用的函数。你自己在函数内部调用普通工具函数时，需要按 Python 规则调用。

```python
def normalize_name(name: str) -> str:
    return name.strip().title()


async def fetch_profile(user_id: int) -> dict[str, str]:
    return {"id": str(user_id), "name": "alice"}
```

在 `async def` 路径函数中：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/profiles/{user_id}")
async def read_profile(user_id: int):
    profile = await fetch_profile(user_id)
    profile["name"] = normalize_name(profile["name"])
    return profile
```

要点：

- 调用普通函数不需要 `await`。
- 调用异步函数必须 `await`，否则拿到的是协程对象，不是最终结果。
- FastAPI 不会自动帮你 await 一个你自己忘记 await 的内部函数调用。

## 18. CPU 密集任务与并行

`async` 主要解决 I/O 等待，不会让 CPU 密集计算变快。下面这种任务即使写在 `async def` 中，也会长时间占用 CPU：

```python
def calculate_score(data: list[int]) -> int:
    total = 0
    for value in data:
        total += value * value
    return total
```

如果在请求处理过程中直接执行大型 CPU 密集任务，请求延迟会变高，也可能影响其他请求。

可选方案：

- 小型 CPU 任务可以直接执行，但要确认耗时可控。
- 中等任务可以使用进程池。
- 长任务应交给任务队列，例如 Celery、RQ、Dramatiq 或独立 worker。
- 机器学习推理可以拆成独立推理服务，由 FastAPI 负责请求编排。
- 部署时使用多个 Uvicorn/Gunicorn worker，让多个进程利用多核。

进程池示例：

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI

app = FastAPI()
process_pool = ProcessPoolExecutor()


def heavy_compute(n: int) -> int:
    total = 0
    for value in range(n):
        total += value * value
    return total


@app.get("/compute")
async def compute(n: int = 10_000_000):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(process_pool, heavy_compute, n)
    return {"result": result}
```

注意：进程池和全局资源需要结合应用生命周期管理，生产环境中要考虑进程退出、资源释放和 worker 数量。

## 19. async 常见错误与修正

### 19.1 忘记 await

错误：

```python
async def load_user(user_id: int) -> dict[str, int]:
    return {"id": user_id}


async def endpoint():
    user = load_user(1)
    return user
```

`user` 是协程对象，不是字典。

修正：

```python
async def endpoint():
    user = await load_user(1)
    return user
```

### 19.2 在 async def 中使用同步 HTTP 客户端

错误：

```python
import requests
from fastapi import FastAPI

app = FastAPI()


@app.get("/bad")
async def bad():
    response = requests.get("https://api.example.com/data", timeout=5)
    return response.json()
```

修正方式一，改用异步客户端：

```python
import httpx
from fastapi import FastAPI

app = FastAPI()


@app.get("/good")
async def good():
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get("https://api.example.com/data")
    response.raise_for_status()
    return response.json()
```

修正方式二，如果必须使用同步客户端，把路径函数改为普通 `def`：

```python
import requests
from fastapi import FastAPI

app = FastAPI()


@app.get("/sync-ok")
def sync_ok():
    response = requests.get("https://api.example.com/data", timeout=5)
    response.raise_for_status()
    return response.json()
```

### 19.3 在请求函数中调用 asyncio.run

错误：

```python
import asyncio


async def load_data() -> dict[str, str]:
    return {"status": "ok"}


async def endpoint():
    data = asyncio.run(load_data())
    return data
```

ASGI 服务本身已经在事件循环中运行。请求处理函数里不应该再用 `asyncio.run()` 创建新的事件循环。

修正：

```python
async def endpoint():
    data = await load_data()
    return data
```

### 19.4 无限制创建后台任务

不建议在请求中随意 `asyncio.create_task()` 后就不再管理：

```python
import asyncio


async def send_event() -> None:
    ...


async def endpoint():
    asyncio.create_task(send_event())
    return {"accepted": True}
```

这种任务的异常、生命周期、服务关闭时的清理都容易失控。更稳妥的做法是使用 FastAPI 的 `BackgroundTasks` 处理轻量后台动作，或者使用任务队列处理重要任务。

## 20. FastAPI 中 def 与 async def 的选择速查

| 场景 | 推荐写法 | 原因 |
| --- | --- | --- |
| 使用异步数据库客户端 | `async def` | 需要 `await` 数据库调用 |
| 使用 `httpx.AsyncClient` | `async def` | HTTP 请求期间可让出事件循环 |
| 使用同步 `requests` | `def` | FastAPI 会在线程池执行同步路径函数 |
| 使用同步 ORM | `def` 或迁移到异步 ORM | 避免在事件循环中阻塞 |
| 简单内存计算，耗时很短 | `def` 或 `async def` 均可 | 影响通常很小，按调用链选择 |
| 大型 CPU 密集计算 | 进程池或任务队列 | async 不能提升 CPU 算力 |
| 依赖函数需要 await | `async def` 依赖 | FastAPI 会 await |
| 依赖函数调用同步阻塞库 | `def` 依赖 | FastAPI 会放入线程池 |

## 21. 类型提示与 async 综合示例

下面示例把类型提示、Pydantic、`Annotated`、异步 HTTP 调用和依赖注入放在一起。

```python
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

app = FastAPI()


class Repo(BaseModel):
    name: str
    full_name: str
    stars: int = Field(alias="stargazers_count")
    language: str | None = None


async def get_github_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if authorization is None:
        return None
    return authorization.removeprefix("Bearer ").strip()


async def github_get(
    client: httpx.AsyncClient,
    url: str,
    token: str | None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.get(url, headers=headers)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub resource not found")

    response.raise_for_status()
    return response.json()


@app.get("/github/{owner}/repos", response_model=list[Repo])
async def list_repos(
    owner: Annotated[str, Path(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    token: Annotated[str | None, Depends(get_github_token)] = None,
):
    url = f"https://api.github.com/users/{owner}/repos?per_page={limit}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        data = await github_get(client, url, token)

    return data
```

这个示例中：

- `owner: Annotated[str, Path(min_length=1)]` 描述路径参数和校验规则。
- `limit: Annotated[int, Query(ge=1, le=100)] = 30` 描述查询参数、范围和默认值。
- `token: Annotated[str | None, Depends(get_github_token)]` 描述依赖注入返回值。
- `response_model=list[Repo]` 描述响应结构。
- `httpx.AsyncClient` 配合 `await` 避免阻塞事件循环。

## 22. 总结

FastAPI 的设计把 Python 类型提示提升为接口契约的一部分。类型提示不只是“注释”，它直接影响请求解析、校验、错误响应、OpenAPI 文档和编辑器体验。写得越准确，FastAPI 能自动完成的事情就越多。

`async` 的核心价值是提升 I/O 密集型 Web 服务的并发能力。使用异步库时，用 `async def` 和 `await`；使用同步阻塞库时，普通 `def` 在 FastAPI 中通常更合适，因为框架会把它放入线程池执行。CPU 密集任务不要指望 `async` 自动加速，应使用多进程、任务队列或独立服务。

最实用的判断方式是：

- 先用类型提示把数据结构描述准确。
- 需要 await 的调用链使用 `async def`。
- 同步阻塞调用不要直接塞进 `async def`。
- I/O 密集靠 async 并发，CPU 密集靠并行或任务拆分。
- 对外 API 使用 Pydantic 模型和 `response_model` 明确契约。
