"""把本地文本文件转换为可检索向量块。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..errors import StorageError
from .chunker import TextChunker
from .embeddings import EmbeddingProvider
from .models import TextDocument
from .vector_store import SQLiteVectorStore

_TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".json", ".py"}
_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class IndexResult:
    indexed: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = ()


class DocumentIndexer:
    def __init__(
        self,
        *,
        workspace_root: Path,
        chunker: TextChunker,
        embeddings: EmbeddingProvider,
        vector_store: SQLiteVectorStore,
    ) -> None:
        self._root = workspace_root.expanduser().resolve()
        self._chunker = chunker
        self._embeddings = embeddings
        self._store = vector_store

    def index_paths(self, paths: Iterable[Path]) -> IndexResult:
        indexed = unchanged = skipped = 0
        errors: list[str] = []
        for file_path in self._iter_files(paths):
            try:
                status = self.index_file(file_path)
                if status == "indexed":
                    indexed += 1
                elif status == "unchanged":
                    unchanged += 1
                else:
                    skipped += 1
            except Exception as error:
                errors.append(f"{file_path}: {error}")
        return IndexResult(indexed, unchanged, skipped, tuple(errors))

    def index_file(self, path: Path) -> str:
        actual_path = path.expanduser().resolve(strict=True)
        try:
            relative_path = actual_path.relative_to(self._root)
        except ValueError as error:
            raise StorageError(f"拒绝索引工作区之外的文件：{path}") from error
        if not actual_path.is_file() or actual_path.suffix.lower() not in _TEXT_EXTENSIONS:
            return "skipped"
        if actual_path.stat().st_size > _MAX_DOCUMENT_BYTES:
            return "skipped"

        with actual_path.open("rb") as file:
            raw = file.read(_MAX_DOCUMENT_BYTES + 1)
        if len(raw) > _MAX_DOCUMENT_BYTES:
            return "skipped"
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise StorageError("文件不是 UTF-8 文本") from error
        content_hash = hashlib.sha256(raw).hexdigest()
        source_uri = actual_path.as_uri()
        document_id = hashlib.sha256(source_uri.encode("utf-8")).hexdigest()[:24]
        if self._store.get_content_hash(document_id) == content_hash:
            return "unchanged"

        chunks = self._chunker.split(content)
        if not chunks:
            return "skipped"
        vectors = self._embeddings.embed([chunk.content for chunk in chunks])
        document = TextDocument(
            document_id=document_id,
            title=relative_path.as_posix(),
            source_uri=source_uri,
            content=content,
            content_hash=content_hash,
        )
        self._store.replace_document(document, chunks, vectors)
        return "indexed"

    def _iter_files(self, paths: Iterable[Path]) -> Iterable[Path]:
        for path in paths:
            candidate = path if path.is_absolute() else self._root / path
            if candidate.is_dir():
                yield from sorted(item for item in candidate.rglob("*") if item.is_file())
            else:
                yield candidate
