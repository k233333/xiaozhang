"""小张守护进程入口（v2.0）

启动顺序：
  1. 配置 + 日志
  2. 初始化记忆库
  3. ResourceManager 启动 watchdog（按当前模式加载本地模型）
  4. 状态机 + 托盘
  5. 唤醒词监听协程（如启用）
  6. 主循环：唤醒 → 录音 → STT → 路由 → 执行
"""
from __future__ import annotations

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from src.core.config import settings
from src.core.logger import get_logger, new_trace_id, setup_logging
from src.core.state_machine import State, StateMachine

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """小张 — Windows 桌面语音助手 v2.0"""
    setup_logging()
    if ctx.invoked_subcommand is None:
        ctx.invoke(start)


@cli.command("start")
def start() -> None:
    """启动守护进程"""
    asyncio.run(_run_daemon())


@cli.command("console")
def console_cmd() -> None:
    """开发期 REPL（键盘代替麦克风）"""
    from dev_console import main as dev_main  # noqa: PLC0415
    asyncio.run(dev_main())


@cli.command("speak")
@click.argument("text", nargs=-1, required=True)
def speak(text: tuple[str, ...]) -> None:
    """单条文本测试整条链路"""
    full = " ".join(text)
    asyncio.run(_speak_once(full))


@cli.command("list-mics")
def list_mics() -> None:
    from src.audio.recorder import list_input_devices  # noqa: PLC0415
    devs = list_input_devices()
    for d in devs:
        console.print(
            f"[bold]#{d['index']}[/bold]  {d['name']}  "
            f"channels={d['channels']}  sr={d['default_samplerate']:.0f}"
        )


@cli.command("init-db")
def init_db_cmd() -> None:
    from src.memory import store  # noqa: PLC0415
    store.init_db()
    console.print(f"[green]已初始化记忆库[/green]: {settings.paths.memory_db}")


@cli.command("evolve")
def evolve_cmd() -> None:
    """根据成功率重写低质量 skill 的 trigger"""
    from src.learning.evolution import evolve_low_quality_skills  # noqa: PLC0415
    changed = asyncio.run(evolve_low_quality_skills())
    if not changed:
        console.print("[dim]没有需要进化的 skill[/dim]")
    else:
        console.print(f"[green]已重写 {len(changed)} 个 skill[/green]: {changed}")


@cli.command("status")
def status_cmd() -> None:
    """查看资源状态：当前模式 / 各本地模型加载情况 / CPU 内存"""
    from src.core.cpu_guard import cpu_load_pct, memory_pressure  # noqa: PLC0415
    from src.core.game_detector import detector  # noqa: PLC0415
    from src.core.resource_manager import resource_manager  # noqa: PLC0415
    from src.local_models.base import available_providers  # noqa: PLC0415

    console.print(f"\n[bold cyan]当前模式：[/bold cyan]{resource_manager.mode.value}")
    state = detector.check_once()
    console.print(
        f"[dim]游戏检测：is_game={state.is_game} method={state.matched_method or '-'} "
        f"fg={state.fg_process or '-'}[/dim]"
    )
    console.print(f"[dim]ONNX providers：{available_providers()}[/dim]")
    cpu = cpu_load_pct(0.2)
    mem = memory_pressure()
    console.print(f"[dim]CPU {cpu:.1f}%   内存 {mem['used_gb']}/{mem['total_gb']}GB[/dim]\n")

    table = Table("model", "loaded", "backend", "providers")
    for name, m in resource_manager._models.items():
        loaded = "[green]✓[/green]" if m.is_loaded() else "[dim]✗[/dim]"
        table.add_row(name, loaded, m.cfg.backend, ", ".join(m.providers))
    console.print(table)


@cli.command("mode")
@click.argument("target", type=click.Choice(["standard", "gaming", "auto"]))
def mode_cmd(target: str) -> None:
    """手动切模式"""
    from src.core.resource_manager import Mode, resource_manager  # noqa: PLC0415

    if target == "auto":
        resource_manager.force_mode(None)
        console.print("[green]已切回自动模式[/green]")
    else:
        m = Mode(target)
        resource_manager.force_mode(m)
        console.print(f"[green]已强制切到 {target} 模式[/green]")


# ---------- 内部 ----------

async def _speak_once(text: str) -> None:
    from src.memory import store  # noqa: PLC0415
    from src.runtime import run_turn  # noqa: PLC0415

    store.init_db()
    new_trace_id()
    console.print(f"[cyan]模拟输入：[/cyan]{text}")
    result = await run_turn(text)
    console.print(f"\n[bold]意图：[/bold]{result.plan.intent if result.plan else '无'}")
    console.print(f"[bold]Skill 命中：[/bold]{'是' if result.skill_hit else '否'}")
    console.print(f"[bold]结果：[/bold]{'✅ 成功' if result.success else '❌ 失败'}")
    if result.report is not None:
        for sr in result.report.steps:
            tag = "[green]OK[/green]" if sr.success else "[red]FAIL[/red]"
            console.print(
                f"  {tag} [{sr.final_tier}] {sr.step.action} "
                f"({sr.elapsed_sec:.2f}s) {sr.message}"
            )


async def _run_daemon() -> None:
    from src.audio import stt, wake_word, recorder  # noqa: PLC0415
    from src.core.resource_manager import resource_manager  # noqa: PLC0415
    from src.memory import store  # noqa: PLC0415
    from src.runtime import run_turn  # noqa: PLC0415
    from src.tray.tray_icon import TrayManager  # noqa: PLC0415

    log = get_logger("main")
    store.init_db()

    sm = StateMachine()
    tray: Optional[TrayManager] = None
    try:
        tray = TrayManager(sm)
        tray.start()
        sm.add_listener(lambda old, new: tray.update_state_icon(new))
    except Exception as e:  # noqa: BLE001
        log.warning("托盘启动失败，继续无托盘", err=str(e))

    await resource_manager.start_watchdog()

    try:
        await stt.warm_up()
    except Exception as e:  # noqa: BLE001
        log.warning("STT 预热失败", err=str(e))

    if settings.wake_word.enabled:
        wd = wake_word.WakeWordDetector(sm)
        wake_task = asyncio.create_task(wd.run(), name="wake")
    else:
        wake_task = None
        log.info("唤醒词禁用 — 进入键盘 push-to-talk 模式（按回车开始说话）")

    try:
        while True:
            if not settings.wake_word.enabled:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: input("\n[按回车开始说话，Ctrl+C 退出] ")
                )
                await sm.transition(State.LISTENING)

            while sm.state != State.LISTENING:
                await asyncio.sleep(0.1)

            chunk = await recorder.record_once_async()
            if chunk is None:
                await sm.reset()
                continue

            tr = await stt.transcribe(chunk.samples, chunk.sample_rate)
            if tr is None or not tr.text.strip():
                console.print("[dim]未识别到语音，回到 IDLE[/dim]")
                await sm.reset()
                continue

            console.print(f"[cyan]你说：[/cyan]{tr.text}")
            result = await run_turn(tr.text, sm=sm)
            console.print(
                f"[bold]结果：[/bold]{'✅ 成功' if result.success else '❌ 失败'}"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]退出守护[/yellow]")
    finally:
        if wake_task:
            wake_task.cancel()
        await resource_manager.stop_watchdog()
        if tray is not None:
            tray.stop()


if __name__ == "__main__":
    cli()
