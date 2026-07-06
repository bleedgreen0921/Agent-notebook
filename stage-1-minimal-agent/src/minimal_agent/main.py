"""命令行入口：普通对话模式和 Agent 模式。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent.loop import AgentEvent, AgentLoop, AgentLoopOptions
from .chat.simple_chat import SimpleChatSession
from .config import load_config
from .llm.openai_compatible_client import OpenAICompatibleClient
from .tools.calculator import CalculatorTool
from .tools.read_file import ReadFileTool
from .tools.registry import ToolRegistry


def main() -> int:
    """执行 CLI，并用进程退出码表示成功或失败。"""

    try:
        args = _parse_arguments()
        task = " ".join(args.task).strip() or input("请输入任务：").strip()
        if not task:
            raise ValueError("任务不能为空")

        config = load_config()
        llm = OpenAICompatibleClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            model=config.llm.model,
            default_timeout_ms=config.llm.timeout_ms,
        )

        if args.chat:
            chat = SimpleChatSession(llm)
            print(chat.send(task))
            return 0

        workspace_root = Path(
            os.environ.get("AGENT_WORKSPACE_ROOT", str(Path.cwd()))
        )
        with ToolRegistry(
            workspace_root=workspace_root,
            default_timeout_ms=config.agent.tool_timeout_ms,
        ) as registry:
            registry.register(CalculatorTool())
            registry.register(ReadFileTool())
            agent = AgentLoop(
                llm=llm,
                tools=registry,
                options=AgentLoopOptions(
                    max_steps=config.agent.max_steps,
                    timeout_ms=config.agent.timeout_ms,
                    llm_timeout_ms=config.llm.timeout_ms,
                    tool_timeout_ms=config.agent.tool_timeout_ms,
                ),
                on_event=_log_event,
            )
            result = agent.run(task)
            print(f"\n最终答案：\n{result.answer}")
            return 0
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"执行失败：{error}", file=sys.stderr)
        return 1


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 1 最小 Agent Loop")
    parser.add_argument(
        "--chat",
        action="store_true",
        help="使用普通对话模式，不启用工具",
    )
    parser.add_argument("task", nargs="*", help="要交给模型处理的任务")
    return parser.parse_args()


def _log_event(event: AgentEvent) -> None:
    """只打印关键 trace，不打印 API Key 或完整系统提示词。"""

    if event.type == "step_started":
        print(f"[step {event.step}] 请求模型决策", file=sys.stderr)
    elif event.type == "protocol_error":
        print(f"[step {event.step}] 协议错误：{event.content}", file=sys.stderr)
    elif event.type == "tool_finished" and event.tool_result is not None:
        status = "成功" if event.tool_result.ok else "失败"
        print(
            f"[step {event.step}] 工具 {event.tool_result.tool_name}："
            f"{status}（{event.tool_result.duration_ms}ms）",
            file=sys.stderr,
        )
    elif event.type == "finished":
        print(f"[step {event.step}] Agent 完成", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
