"""可替换的 embedding 提供器。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import socket
from typing import Any, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..errors import EmbeddingError

_TOKEN_PATTERN = re.compile(r"[\w]+|[^\w\s]", flags=re.UNICODE)
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """
    无网络依赖的教学型向量器。

    它通过稳定哈希把词元映射到固定维度，适合验证 RAG 数据流；语义质量
    不及专业 embedding 模型，生产使用应切换 OpenAIEmbeddingProvider。
    """

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions 必须大于 0")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        lowered = text.lower()
        tokens = _TOKEN_PATTERN.findall(lowered)
        # 中文通常没有空格，补充字符二元组以提升局部词语的重合召回。
        compact = "".join(character for character in lowered if not character.isspace())
        tokens.extend(compact[index : index + 2] for index in range(max(0, len(compact) - 1)))
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "big")
            index = number % self._dimensions
            sign = 1.0 if number & 1 else -1.0
            vector[index] += sign
        return _normalize(vector)


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_ms: int = 30_000,
    ) -> None:
        if dimensions <= 0 or timeout_ms <= 0:
            raise ValueError("dimensions 和 timeout_ms 必须大于 0")
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout_ms = timeout_ms

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        body = json.dumps(
            {
                "model": self._model,
                "input": list(texts),
                "dimensions": self._dimensions,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_ms / 1_000) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            detail = error.read(1_001).decode("utf-8", errors="replace")[:1_000]
            raise EmbeddingError(
                f"Embedding API 请求失败（HTTP {error.code}）：{detail}"
            ) from error
        except (URLError, TimeoutError, socket.timeout, OSError) as error:
            raise EmbeddingError(f"Embedding API 请求异常：{error}") from error
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise EmbeddingError("Embedding API 响应过大")

        try:
            payload: Any = json.loads(raw.decode("utf-8"))
            data = payload["data"]
            ordered = sorted(data, key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise EmbeddingError("Embedding API 响应结构不合法") from error
        if len(vectors) != len(texts):
            raise EmbeddingError("Embedding API 返回向量数量不匹配")

        validated: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self._dimensions:
                raise EmbeddingError("Embedding API 返回向量维度不匹配")
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in vector
            ):
                raise EmbeddingError("Embedding 向量包含非数值元素")
            validated.append([float(value) for value in vector])
        return validated


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return vector if magnitude == 0 else [value / magnitude for value in vector]
