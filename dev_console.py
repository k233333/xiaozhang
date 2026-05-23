"""开发期 REPL：键盘输入代替麦克风，直接走完整链路

不启动唤醒词、不启动音频流，最适合开发期 D3-D9 阶段调试。

用法：
    uv run python dev_console.py
"""
from __future__ import annotations

import asyncio

from rich.console import Console

from src.core.logger import setup_logging
from src.memory import store
from src.runtime import run_turn

console = Console()


async def main() -> None:
    setup_logging()
    store.init_db()
    console.print("[bold cyan]小张开发控制台[/bold cyan]")
    console.print("输入文字代替语音；输入 [yellow]:q[/yellow] 退出，[yellow]:tokens[/yellow] 查看消耗。\n")

    from src.core.token_tracker import tracker  # noqa: PLC0415

    while True:
        try:
            text = await asyncio.get_running_loop().run_in_executor(
                None, lambda: input("你 > ")
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见")
            break
        text = text.strip()
        if text in (":q", ":quit", "exit", "quit"):
            break
        if text == ":tokens":
            console.print(tracker.summary())
            continue
        if not text:
            continue

        result = await run_turn(text)
        if result.skill_hit:
            console.print("[green]\\[skill 命中][/green]")
        if result.note:
            console.print(f"[dim]→ {result.note}[/dim]")
        if result.report is not None:
            for sr in result.report.steps:
                color = "green" if sr.success else "red"
                console.print(
                    f"  [{color}]{sr.final_tier}[/{color}] {sr.step.action} "
                    f"({sr.elapsed_sec:.2f}s) {sr.message}"
                )
        console.print(
            f"[bold]结果：[/bold]{'[green]成功[/green]' if result.success else '[red]失败[/red]'}"
            f"  [dim]{tracker.summary_oneliner()}[/dim]\n"
        )


if __name__ == "__main__":
    asyncio.run(main())
