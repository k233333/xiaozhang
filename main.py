"""小张守护进程入口（v2.0）

启动顺序：
  1. 配置 + 日志
  2. 初始化记忆库
  3. ResourceManager 启动 watchdog（按当前模式加载本地模型）
  4. 状态机 + 托盘
  5. 唤醒词监听协程（如启用）
  6. 主循环：唤醒 → 录音 → STT → 路由 → 执行

CLI 结构（v2.0+）：
  xiaozhang start            常驻守护
  xiaozhang console          开发期 REPL（键盘代麦克风）
  xiaozhang speak <text>     单条文本测试
  xiaozhang status           资源 + 模式 + 模型 + cpu_guard
  xiaozhang mode <target>    手动切 standard/gaming/auto

  xiaozhang audio  list      列出输入设备
  xiaozhang memory init      初始化记忆库
  xiaozhang skills list      列出所有 skill
  xiaozhang skills stats     skill 调用成功率
  xiaozhang skills show <n>  查看 skill 完整内容
  xiaozhang skills delete <n> 删除 skill（仅 _generated）
  xiaozhang skills evolve    重写低质量 skill 的 trigger

旧命令兼容（deprecated 但仍可用）：
  list-mics  → audio list
  init-db    → memory init
  stats      → skills stats
  skills     → skills list
  evolve     → skills evolve
"""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

# Windows GBK 控制台 → 强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import click
from rich.console import Console
from rich.table import Table

from src.core.config import settings
from src.core.logger import get_logger, new_trace_id, setup_logging
from src.core.state_machine import State, StateMachine

console = Console()


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """小张 — Windows 桌面语音助手 v2.0"""
    setup_logging()
    if ctx.invoked_subcommand is None:
        ctx.invoke(start)


# ============================================================
# 顶层命令（最常用）
# ============================================================

@cli.command("start")
def start() -> None:
    """启动守护进程（含 watchdog + cpu_guard + 托盘）"""
    asyncio.run(_run_daemon())


@cli.command("console")
def console_cmd() -> None:
    """开发期 REPL（键盘代替麦克风）"""
    from dev_console import main as dev_main  # noqa: PLC0415
    asyncio.run(dev_main())


@cli.command("speak")
@click.argument("text", nargs=-1, required=True)
def speak(text: tuple[str, ...]) -> None:
    """单条文本测试整条链路（不需要麦克风）"""
    asyncio.run(_speak_once(" ".join(text)))


@cli.command("status")
def status_cmd() -> None:
    """查看资源状态：模式 / 本地模型 / CPU 内存 / cpu_guard"""
    from src.core.cpu_guard import cpu_load_pct, get_guard_state, memory_pressure  # noqa: PLC0415
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
    console.print(f"[dim]CPU {cpu:.1f}%   内存 {mem['used_gb']}/{mem['total_gb']}GB[/dim]")
    gs = get_guard_state()
    if gs["samples_count"]:
        console.print(
            f"[dim]cpu_guard：连续高={gs['consecutive_high']} 连续低={gs['consecutive_low']} "
            f"已触发游戏模式={gs['triggered_gaming']} 最近5次={gs['recent_cpu']}%[/dim]"
        )
    console.print()

    table = Table("model", "loaded", "backend", "providers")
    for name, m in resource_manager._models.items():
        loaded = "[green]on[/green]" if m.is_loaded() else "[dim]off[/dim]"
        table.add_row(name, loaded, m.cfg.backend, ", ".join(m.providers))
    console.print(table)


@cli.command("mode")
@click.argument("target", type=click.Choice(["standard", "gaming", "auto"]))
def mode_cmd(target: str) -> None:
    """手动切模式：standard / gaming / auto"""
    from src.core.resource_manager import Mode, resource_manager  # noqa: PLC0415

    if target == "auto":
        resource_manager.force_mode(None)
        console.print("[green]已切回自动模式[/green]")
    else:
        resource_manager.force_mode(Mode(target))
        console.print(f"[green]已强制切到 {target} 模式[/green]")


# ============================================================
# audio 子组
# ============================================================

@cli.group("audio")
def audio_group() -> None:
    """音频设备管理"""


@audio_group.command("list")
def audio_list() -> None:
    """列出可用输入设备"""
    from src.audio.recorder import list_input_devices  # noqa: PLC0415
    devs = list_input_devices()
    if not devs:
        console.print("[red]没有检测到输入设备[/red]")
        return
    table = Table("index", "name", "channels", "sr")
    for d in devs:
        table.add_row(
            str(d["index"]), d["name"], str(d["channels"]), f"{d['default_samplerate']:.0f}"
        )
    console.print(table)
    console.print(f"\n[dim]共 {len(devs)} 个输入设备[/dim]")


# ============================================================
# memory 子组
# ============================================================

@cli.group("memory")
def memory_group() -> None:
    """记忆库管理"""


@memory_group.command("init")
def memory_init() -> None:
    """初始化记忆库 schema"""
    from src.memory import store  # noqa: PLC0415
    store.init_db()
    console.print(f"[green]已初始化记忆库[/green]: {settings.paths.memory_db}")


@memory_group.command("recent")
@click.option("--limit", default=10, type=int, help="显示最近 N 条会话")
def memory_recent(limit: int) -> None:
    """查看最近的会话历史"""
    from src.memory import store  # noqa: PLC0415
    sessions = store.recent_sessions(limit=limit)
    if not sessions:
        console.print("[dim]还没有会话记录[/dim]")
        return
    import time
    table = Table("时间", "意图", "命中", "成功", "用户输入")
    for s in sessions:
        ts = time.strftime("%m-%d %H:%M", time.localtime(s.get("started_at", 0)))
        ok = "[green]y[/green]" if s.get("success") else "[red]n[/red]"
        hit = "[cyan]y[/cyan]" if s.get("skill_hit") else "."
        table.add_row(
            ts,
            s.get("intent", "") or "-",
            hit,
            ok,
            (s.get("user_text") or "")[:40],
        )
    console.print(table)


@memory_group.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", default=10, type=int)
def memory_search(query: tuple[str, ...], limit: int) -> None:
    """全文搜索事件流（中英文都行）"""
    from src.memory import store  # noqa: PLC0415
    q = " ".join(query)
    rows = store.search_events(q, limit=limit)
    if not rows:
        console.print(f"[dim]没找到匹配 [{q}] 的事件[/dim]")
        return
    import time
    for r in rows:
        ts = time.strftime("%m-%d %H:%M", time.localtime(r.get("ts", 0)))
        console.print(f"[dim]{ts}[/dim]  [{r['kind']}]  {r['text']}")


# ============================================================
# skills 子组
# ============================================================

@cli.group("skills")
def skills_group() -> None:
    """Skills 管理（学习能力的核心数据）"""


@skills_group.command("list")
def skills_list() -> None:
    """列出所有已加载的 skill"""
    from src.skills import loader  # noqa: PLC0415

    skills = loader.load_all()
    if not skills:
        console.print("[dim]没有任何 skill[/dim]")
        return
    table = Table("name", "triggers", "steps", "source")
    for s in skills:
        source = "[cyan]_generated[/cyan]" if "_generated" in str(s.path) else "_builtin"
        triggers = " / ".join(s.triggers[:3])
        if len(s.triggers) > 3:
            triggers += f" (+{len(s.triggers) - 3})"
        table.add_row(s.name, triggers, str(len(s.steps)), source)
    console.print(table)
    console.print(f"\n[dim]共 {len(skills)} 个 skill[/dim]")


@skills_group.command("stats")
def skills_stats() -> None:
    """查看 skill 调用成功率（自学习成果）"""
    from src.learning import skill_stats  # noqa: PLC0415

    stats = skill_stats.all_stats()
    if not stats:
        console.print("[dim]还没有 skill 调用记录[/dim]")
        return
    table = Table("skill", "total", "success", "fail", "rate", "last_failure")
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1].get("total", 0)):
        total = s.get("total", 0)
        succ = s.get("success", 0)
        fail = s.get("fail", 0)
        rate = succ / total if total else 0
        rate_color = "green" if rate >= 0.8 else ("yellow" if rate >= 0.5 else "red")
        table.add_row(
            name,
            str(total),
            str(succ),
            str(fail),
            f"[{rate_color}]{rate:.0%}[/{rate_color}]",
            (s.get("last_failure_reason") or "")[:40],
        )
    console.print(table)


@skills_group.command("show")
@click.argument("name")
def skills_show(name: str) -> None:
    """查看指定 skill 的完整 SKILL.md 内容"""
    from src.skills import loader  # noqa: PLC0415

    skills = loader.load_all()
    target = next((s for s in skills if s.name == name), None)
    if target is None:
        # 模糊匹配
        candidates = [s for s in skills if name.lower() in s.name.lower()]
        if not candidates:
            console.print(f"[red]找不到 skill：{name}[/red]")
            console.print("[dim]可用 skill：[/dim]")
            for s in skills:
                console.print(f"  - {s.name}")
            return
        if len(candidates) > 1:
            console.print(f"[yellow]模糊匹配到多个：[/yellow]")
            for s in candidates:
                console.print(f"  - {s.name}")
            return
        target = candidates[0]
    md_path = target.path / "SKILL.md"
    console.print(f"[bold]{target.name}[/bold]  [dim]@ {md_path}[/dim]\n")
    console.print(md_path.read_text(encoding="utf-8"))


@skills_group.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="跳过确认")
def skills_delete(name: str, force: bool) -> None:
    """删除指定 skill（仅 _generated 下的；_builtin 受保护）"""
    import shutil  # noqa: PLC0415

    from src.skills import loader  # noqa: PLC0415

    skills = loader.load_all()
    target = next((s for s in skills if s.name == name), None)
    if target is None:
        console.print(f"[red]找不到 skill：{name}[/red]")
        return

    if "_builtin" in str(target.path):
        console.print(
            f"[red]不能删除内置 skill {target.name}[/red]\n"
            f"[dim]如要禁用，请直接删 {target.path}/SKILL.md（不推荐）[/dim]"
        )
        return

    if not force:
        ans = click.confirm(f"确定删除 _generated/{target.name} ？", default=False)
        if not ans:
            console.print("[yellow]已取消[/yellow]")
            return

    shutil.rmtree(target.path)
    console.print(f"[green]已删除[/green] {target.path}")


@skills_group.command("evolve")
def skills_evolve() -> None:
    """重写成功率 < 50% 的 skill 的 trigger（基于最近失败原话让 LLM 优化）"""
    from src.learning.evolution import evolve_low_quality_skills  # noqa: PLC0415
    changed = asyncio.run(evolve_low_quality_skills())
    if not changed:
        console.print("[dim]没有需要进化的 skill（满足条件：≥5 次调用且成功率 <50%）[/dim]")
    else:
        console.print(f"[green]已重写 {len(changed)} 个 skill[/green]: {changed}")


# ============================================================
# 旧命令兼容（deprecated 但仍能用）
# ============================================================

@cli.command("list-mics", hidden=True)
@click.pass_context
def _legacy_list_mics(ctx: click.Context) -> None:
    """[deprecated] 用 'audio list' 代替"""
    console.print("[yellow]提示：'list-mics' 已重命名为 'audio list'[/yellow]")
    ctx.invoke(audio_list)


@cli.command("init-db", hidden=True)
@click.pass_context
def _legacy_init_db(ctx: click.Context) -> None:
    """[deprecated] 用 'memory init' 代替"""
    console.print("[yellow]提示：'init-db' 已重命名为 'memory init'[/yellow]")
    ctx.invoke(memory_init)


@cli.command("stats", hidden=True)
@click.pass_context
def _legacy_stats(ctx: click.Context) -> None:
    """[deprecated] 用 'skills stats' 代替"""
    console.print("[yellow]提示：'stats' 已重命名为 'skills stats'[/yellow]")
    ctx.invoke(skills_stats)


@cli.command("skills-list", hidden=True)
@click.pass_context
def _legacy_skills_list(ctx: click.Context) -> None:
    """[deprecated] 用 'skills list' 代替"""
    console.print("[yellow]提示：旧命令已重命名为 'skills list'[/yellow]")
    ctx.invoke(skills_list)


@cli.command("evolve", hidden=True)
@click.pass_context
def _legacy_evolve(ctx: click.Context) -> None:
    """[deprecated] 用 'skills evolve' 代替"""
    console.print("[yellow]提示：'evolve' 已重命名为 'skills evolve'[/yellow]")
    ctx.invoke(skills_evolve)


# ============================================================
# 内部实现
# ============================================================

async def _speak_once(text: str) -> None:
    from src.memory import store  # noqa: PLC0415
    from src.runtime import run_turn  # noqa: PLC0415

    store.init_db()
    new_trace_id()
    console.print(f"[cyan]模拟输入：[/cyan]{text}")
    result = await run_turn(text)
    console.print(f"\n[bold]意图：[/bold]{result.plan.intent if result.plan else '无'}")
    console.print(f"[bold]Skill 命中：[/bold]{'是' if result.skill_hit else '否'}")
    console.print(f"[bold]结果：[/bold]{'[green]成功[/green]' if result.success else '[red]失败[/red]'}")
    if result.report is not None:
        for sr in result.report.steps:
            tag = "[green]OK[/green]" if sr.success else "[red]FAIL[/red]"
            console.print(
                f"  {tag} [{sr.final_tier}] {sr.step.action} "
                f"({sr.elapsed_sec:.2f}s) {sr.message}"
            )


async def _run_daemon() -> None:
    from src.audio import stt, wake_word, recorder  # noqa: PLC0415
    from src.core.cpu_guard import start_cpu_guard, stop_cpu_guard  # noqa: PLC0415
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
    await start_cpu_guard()

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
                f"[bold]结果：[/bold]{'[green]成功[/green]' if result.success else '[red]失败[/red]'}"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]退出守护[/yellow]")
    finally:
        if wake_task:
            wake_task.cancel()
        await resource_manager.stop_watchdog()
        await stop_cpu_guard()
        if tray is not None:
            tray.stop()


if __name__ == "__main__":
    cli()
