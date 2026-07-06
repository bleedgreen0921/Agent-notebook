"""Stage 2 研究助手 CLI：索引资料、提问和写入长期记忆。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent.loop import ResearchAgent, ResearchAgentOptions, ResearchEvent
from .config import AppConfig, load_config
from .llm.openai_compatible_client import OpenAICompatibleClient
from .memory.long_term import LongTermMemoryStore
from .memory.session import SessionMemoryStore
from .rag.chunker import TextChunker
from .rag.embeddings import (
    EmbeddingProvider,
    HashEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from .rag.indexer import DocumentIndexer
from .rag.retriever import Retriever
from .rag.vector_store import SQLiteVectorStore
from .storage.database import Database
from .tools.browser_fetch import BrowserFetchTool
from .tools.code_execution import RestrictedPythonTool
from .tools.database_query import DatabaseQueryTool
from .tools.file_search import FileSearchTool
from .tools.memory_tools import RecallMemoryTool, SaveMemoryTool
from .tools.rag_search import RAGSearchTool
from .tools.registry import ToolRegistry
from .tools.web_search import WebSearchTool


def main() -> int:
    try:
        args = _parser().parse_args()
        config = load_config(require_llm=args.command == "ask")
        database = Database(config.data_dir / "research-agent.sqlite3")
        database.initialize()
        embeddings = _create_embeddings(config)
        vector_store = SQLiteVectorStore(database)

        if args.command == "index":
            indexer = DocumentIndexer(
                workspace_root=config.workspace_root,
                chunker=TextChunker(),
                embeddings=embeddings,
                vector_store=vector_store,
            )
            result = indexer.index_paths(Path(path) for path in args.paths)
            print(
                f"索引完成：新增/更新 {result.indexed}，未变化 {result.unchanged}，"
                f"跳过 {result.skipped}，错误 {len(result.errors)}"
            )
            for error in result.errors:
                print(f"- {error}", file=sys.stderr)
            return 1 if result.errors else 0

        long_term = LongTermMemoryStore(database, embeddings)
        if args.command == "remember":
            memory_id = long_term.save(
                args.namespace,
                " ".join(args.content),
                {"source": "explicit_cli"},
            )
            print(f"长期记忆已保存：{memory_id}")
            return 0

        return _run_ask(args, config, database, embeddings, vector_store, long_term)
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"执行失败：{error}", file=sys.stderr)
        return 1


def _run_ask(
    args: argparse.Namespace,
    config: AppConfig,
    database: Database,
    embeddings: EmbeddingProvider,
    vector_store: SQLiteVectorStore,
    long_term: LongTermMemoryStore,
) -> int:
    retriever = Retriever(
        embeddings=embeddings,
        vector_store=vector_store,
        default_top_k=config.agent.retrieval_top_k,
        min_score=config.agent.retrieval_min_score,
    )
    llm = OpenAICompatibleClient(
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        model=config.llm.model,
        default_timeout_ms=config.llm.timeout_ms,
    )
    with ToolRegistry(
        workspace_root=config.workspace_root,
        default_timeout_ms=config.agent.tool_timeout_ms,
    ) as tools:
        tools.register(RAGSearchTool(retriever))
        tools.register(WebSearchTool(config.search_api_url))
        tools.register(BrowserFetchTool())
        tools.register(FileSearchTool())
        tools.register(DatabaseQueryTool())
        tools.register(
            RestrictedPythonTool(enabled=config.enable_code_execution)
        )
        tools.register(RecallMemoryTool(long_term, args.namespace))
        tools.register(SaveMemoryTool(long_term, args.namespace))
        agent = ResearchAgent(
            llm=llm,
            tools=tools,
            sessions=SessionMemoryStore(database),
            long_term_memory=long_term,
            options=ResearchAgentOptions(
                max_steps=config.agent.max_steps,
                timeout_ms=config.agent.timeout_ms,
                llm_timeout_ms=config.llm.timeout_ms,
                tool_timeout_ms=config.agent.tool_timeout_ms,
                context_max_chars=config.agent.context_max_chars,
            ),
            on_event=_log_event,
        )
        result = agent.run(
            " ".join(args.task),
            session_id=args.session,
            memory_namespace=args.namespace,
        )
    print(result.answer)
    if result.sources:
        print("\n来源：")
        for source in result.sources:
            locator = f"（{source.locator}）" if source.locator else ""
            print(f"[{source.source_id}] {source.title}{locator} - {source.uri}")
    return 0


def _create_embeddings(config: AppConfig) -> EmbeddingProvider:
    if config.embedding.provider == "local":
        return HashEmbeddingProvider(config.embedding.dimensions)
    return OpenAIEmbeddingProvider(
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        model=config.embedding.model,
        dimensions=config.embedding.dimensions,
        timeout_ms=config.llm.timeout_ms,
    )


def _log_event(event: ResearchEvent) -> None:
    print(f"[step {event.step}] {event.detail}", file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 2 RAG 与记忆研究助手")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="索引工作区文本资料")
    index_parser.add_argument("paths", nargs="+", help="文件或目录路径")

    ask_parser = subparsers.add_parser("ask", help="研究并回答问题")
    ask_parser.add_argument("task", nargs="+", help="研究问题")
    ask_parser.add_argument("--session", default="default", help="会话 ID")
    ask_parser.add_argument("--namespace", default="default", help="长期记忆命名空间")

    memory_parser = subparsers.add_parser("remember", help="显式保存长期记忆")
    memory_parser.add_argument("content", nargs="+", help="需要记住的内容")
    memory_parser.add_argument("--namespace", default="default")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
