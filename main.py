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
@click.option("--probe-load/--no-probe-load", default=True,
              help="探测式加载所有可用本地模型一次后展示（默认开）")
def status_cmd(probe_load: bool) -> None:
    """查看资源状态：模式 / 本地模型 / CPU 内存 / cpu_guard"""
    from src.core.cpu_guard import cpu_load_pct, get_guard_state, memory_pressure  # noqa: PLC0415
    from src.core.game_detector import detector  # noqa: PLC0415
    from src.core.resource_manager import resource_manager  # noqa: PLC0415
    from src.local_models.base import available_providers  # noqa: PLC0415

    if probe_load:
        # 一次性按当前模式尝试加载（仅状态查看用，看完不卸载也无所谓，进程退出自然清）
        resource_manager.load_for_mode(resource_manager.mode)

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
# vision 子组（H 选项）
# ============================================================

@cli.group("vision")
def vision_group() -> None:
    """视觉能力管理"""


@vision_group.command("check")
def vision_check() -> None:
    """检查 vision provider 配置是否就绪"""
    import os  # noqa: PLC0415
    from src.core.config import llm_config  # noqa: PLC0415

    console.print("\n[bold]Vision 路由：[/bold]")
    route = llm_config.routing.get("vision_analysis")
    if route is None:
        console.print("[red]config/llm.yaml 没有配 vision_analysis 路由[/red]")
        return

    targets = [route.primary] + ([route.fallback] if route.fallback else [])
    table = Table("target", "model", "vision", "key 已设", "状态")
    for target in targets:
        try:
            cfg, model_name = llm_config.parse_target(target)
        except (KeyError, ValueError) as e:
            table.add_row(target, "-", "-", "-", f"[red]路由错误：{e}[/red]")
            continue
        has_key = bool(os.getenv(cfg.api_key_env))
        v = "[green]y[/green]" if cfg.supports_vision else "[yellow]n（盲规划）[/yellow]"
        k = "[green]y[/green]" if has_key else f"[red]缺 {cfg.api_key_env}[/red]"
        if cfg.supports_vision and has_key:
            status = "[green]就绪[/green]"
        elif has_key:
            status = "[yellow]能用但走盲规划[/yellow]"
        else:
            status = "[red]无 key[/red]"
        table.add_row(target, model_name, v, k, status)
    console.print(table)


@vision_group.command("test")
@click.argument("intent", nargs=-1)
def vision_test(intent: tuple[str, ...]) -> None:
    """实测 vision 链路（截屏当前屏幕，让 vision provider 决策）"""
    from src.vision.vision_query import decide_from_screen  # noqa: PLC0415

    text = " ".join(intent) or "找出当前屏幕上最显眼的可点击按钮"
    console.print(f"[cyan]测试意图：[/cyan]{text}")
    console.print("[dim]截屏中...[/dim]")
    result = asyncio.run(decide_from_screen(text))
    if result is None:
        console.print("[red]vision 调用失败，看 logs/xiaozhang.log[/red]")
        return
    import json as _json  # noqa: PLC0415
    console.print("[bold]决策：[/bold]")
    console.print(_json.dumps(result, ensure_ascii=False, indent=2))


# ============================================================
# models 子组（本地模型下载/状态）
# ============================================================

@cli.group("models")
def models_group() -> None:
    """本地模型管理（下载、状态）"""


@models_group.command("status")
def models_status() -> None:
    """看本地模型文件下载情况 + ONNX provider"""
    from src.core.config import settings  # noqa: PLC0415
    from src.local_models.base import available_providers, has_directml  # noqa: PLC0415

    providers = available_providers()
    console.print(f"[bold]ONNX Runtime providers：[/bold]{providers}")
    if has_directml():
        console.print("[green]DirectML 可用 — 本地模型会上 GPU[/green]")
    else:
        console.print("[yellow]DirectML 不可用 — 本地模型走 CPU。装 GPU 加速：[/yellow]")
        console.print("  uv sync --extra gpu")
    console.print()

    table = Table("model", "path", "exists", "size")
    for name, cfg in settings.local_models.items():
        p = settings.resolve_path(cfg.model_path)
        if p.is_file():
            size = f"{p.stat().st_size / 1024 / 1024:.1f} MB"
            ok = "[green]y[/green]"
        elif p.is_dir():
            files = list(p.rglob("*.onnx"))
            if files:
                total = sum(f.stat().st_size for f in files)
                size = f"{total / 1024 / 1024:.1f} MB ({len(files)} ONNX)"
                ok = "[green]y[/green]"
            else:
                size = "目录但无 ONNX"
                ok = "[red]n[/red]"
        else:
            size = "-"
            ok = "[red]n[/red]"
        rel = str(p.relative_to(settings.project_root)) if p.is_absolute() else str(p)
        table.add_row(name, rel, ok, size)
    console.print(table)


@models_group.command("download")
@click.option("--vad/--no-vad", default=True, help="下载 Silero VAD（约 2 MB）")
@click.option("--sensevoice/--no-sensevoice", default=False, help="装 funasr 自动拉 SenseVoice（首次约 234 MB）")
@click.option("--omniparser/--no-omniparser", default=False, help="下载 OmniParser-v2（约 1.3 GB，慢）")
def models_download(vad: bool, sensevoice: bool, omniparser: bool) -> None:
    """下载本地模型（默认只下 Silero VAD，其他要显式开）"""
    from src.core.config import settings  # noqa: PLC0415

    if not (vad or sensevoice or omniparser):
        console.print("[yellow]啥都没选，nothing to do[/yellow]")
        return

    if vad:
        _download_silero_vad(settings.resolve_path(settings.paths.models_dir))
    if sensevoice:
        _install_sensevoice()
    if omniparser:
        _download_omniparser(settings.resolve_path(settings.paths.models_dir))

    console.print("\n[bold]再跑 [cyan]xiaozhang models status[/cyan] 看下载结果[/bold]")


def _download_silero_vad(models_dir) -> None:
    import urllib.request  # noqa: PLC0415

    target = models_dir / "silero_vad.onnx"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1024 * 1024:
        console.print(f"[green]Silero VAD 已存在[/green]: {target}")
        return
    url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
    console.print(f"[cyan]下载 Silero VAD[/cyan]: {url}")
    try:
        urllib.request.urlretrieve(url, target)
        size = target.stat().st_size / 1024 / 1024
        console.print(f"[green]Silero VAD 下载完成 {size:.1f} MB[/green]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]下载失败：{e}[/red]")


def _install_sensevoice() -> None:
    console.print(
        "[yellow]SenseVoice 需要先装 funasr。建议跑：[/yellow]"
    )
    console.print("  [cyan]uv sync --extra sensevoice[/cyan]")
    console.print(
        "[dim]装好后首次调用会从 ModelScope 自动下载约 234MB 到 ~/.cache/modelscope[/dim]"
    )


def _download_omniparser(models_dir) -> None:
    console.print(
        "[yellow]OmniParser-v2 较大（约 1.3 GB），推荐手动从 HuggingFace 下：[/yellow]"
    )
    console.print(
        "  https://huggingface.co/microsoft/OmniParser-v2.0"
    )
    console.print(
        f"[dim]下载后放到：{models_dir / 'omniparser_v2'}[/dim]"
    )
    console.print(
        "[dim]目录下应有 icon_detect/model.onnx 和 icon_caption/model.onnx[/dim]"
    )


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
        # 使用自训练唤醒词模型（mel 特征 + ONNX 分类器，99.8% 准确率）
        from src.audio.wake_word_loop import WakeWordLoop  # noqa: PLC0415
        ww_loop = WakeWordLoop(sm)
        wake_task = asyncio.create_task(ww_loop.run(), name="wake_custom")
        log.info("自训练唤醒词监听启动（说'小张'触发）")
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
            else:
                # 唤醒词模式：等 wake_word_loop 把状态切到 LISTENING
                pass

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

            # Hermes 模式：转发给本地 Hermes agent 执行
            _hermes_cfg = getattr(settings, "hermes", None)
            if _hermes_cfg and getattr(_hermes_cfg, "enabled", False):
                from src.hermes_dispatch import dispatch_to_hermes  # noqa: PLC0415
                h_result = await dispatch_to_hermes(tr.text)
                if h_result.output:
                    console.print(f"[bold cyan]Hermes:[/bold cyan] {h_result.output}")
                console.print(
                    f"[bold]结果：[/bold]{'[green]成功[/green]' if h_result.success else '[red]失败[/red]'}"
                )
                await sm.reset()
            else:
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
