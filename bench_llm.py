"""LLM Provider 速度 + 质量基准测试

测试方式：
  - 每个目标用 5 条不同复杂度的真实指令跑 task_planning
  - 记录：首字节延迟（TTFT）、总耗时、输出 token 数、tok/s、JSON 是否合法、规划质量评分
  - 评分维度：tier 标记是否准确、step 数量是否合理、动作字段是否完整

输出：rich 表格 + 推荐配置

用法：
  uv run python bench_llm.py                  # 跑全部已配 key 的 provider
  uv run python bench_llm.py --rounds 3       # 每个组合跑 3 次取平均（更准但慢）
  uv run python bench_llm.py --task simple    # 只跑简单任务
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# 强制 UTF-8 输出（Windows GBK 控制台）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import click
from rich.console import Console
from rich.table import Table

from src.brain.llm_router import _get_provider_client, extract_json
from src.core.config import llm_config

console = Console()


# ===== 测试用例 =====

TEST_CASES = {
    "simple": [
        ("打开抖音", 1),               # 期望 1 步
        ("锁屏", 1),
        ("打开 GitHub", 1),
    ],
    "medium": [
        ("打开抖音搜不惑兄弟最新视频", 2),
        ("打开微信给妈妈发消息说我晚上回来", 3),
    ],
    "complex": [
        ("帮我把今天 D 盘截图整理到桌面按日期分文件夹", 4),
        ("打开 VS Code 然后切到上次的项目并跑测试", 3),
    ],
}

PLANNER_PROMPT = """你是 Windows 桌面语音助手"小张"的规划核心。
把用户指令变成严格 JSON 操作计划，不要任何前后说明，不要 markdown 包裹。

JSON 结构：
{
  "intent": "snake_case",
  "steps": [
    {"tier": "D|C|A", "action": "open_url|launch_app|keys|type|click|wait|say", "...": "..."}
  ]
}

可用 action：open_url(url) / launch_app(cmd 或 url) / keys(keys) / type(text) / click(target) / wait(timeout_seconds) / say(text)
三级 tier：D=URI/快捷键/cmd（最优），C=UIA 控件树，A=Vision 兜底
"""


@dataclass
class RunResult:
    target: str
    user_text: str
    expected_steps: int
    success: bool
    elapsed_sec: float
    output_chars: int
    output_tokens: int = 0       # Groq 返回 usage
    json_valid: bool = False
    intent: str = ""
    actual_steps: int = 0
    quality_score: float = 0.0   # 0-100
    error: str = ""


# ===== 调用 =====

async def call_target(target: str, user_text: str, timeout: int = 30) -> tuple[str, float, int]:
    """调用单个 target，返回 (text, elapsed_sec, output_tokens)"""
    cfg, model = llm_config.parse_target(target)
    provider_name = target.split(".", 1)[0]

    if not cfg.api_key:
        raise RuntimeError(f"缺少 env {cfg.api_key_env}")

    if cfg.sdk != "openai":
        raise RuntimeError(f"benchmark 暂只支持 openai sdk, got {cfg.sdk}")

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()

    def _call():
        client = _get_provider_client(provider_name, cfg)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            timeout=timeout,
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        text = resp.choices[0].message.content or ""
        usage_tokens = 0
        if resp.usage and getattr(resp.usage, "completion_tokens", None):
            usage_tokens = resp.usage.completion_tokens
        return text, usage_tokens

    text, usage = await asyncio.wait_for(
        loop.run_in_executor(None, _call), timeout=timeout
    )
    return text, time.monotonic() - t0, usage


# ===== 评分 =====

def score_plan(raw_text: str, expected_steps: int) -> tuple[bool, str, int, float]:
    """从 LLM 输出评估规划质量
    返回 (json_valid, intent, actual_steps, quality_score)
    """
    data = extract_json(raw_text)
    if data is None:
        return False, "", 0, 0.0

    intent = data.get("intent", "")
    steps = data.get("steps", [])
    actual = len(steps) if isinstance(steps, list) else 0

    score = 0.0
    # JSON 合法 30 分
    score += 30
    # intent 是 snake_case 10 分
    if intent and "_" in intent and intent.islower():
        score += 10
    elif intent:
        score += 5
    # 步数合理（差距 ≤ 1 满 30 分，差 2 半分，更多 0）
    diff = abs(actual - expected_steps)
    if diff == 0:
        score += 30
    elif diff == 1:
        score += 20
    elif diff == 2:
        score += 10
    # 每个 step 必备字段
    if isinstance(steps, list) and steps:
        valid_steps = 0
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get("tier") in ("D", "C", "A") and s.get("action"):
                valid_steps += 1
        score += 30 * (valid_steps / max(1, len(steps)))

    return True, intent, actual, round(score, 1)


# ===== 主流程 =====

async def run_benchmark(targets: list[str], cases: list[tuple[str, int]], rounds: int) -> list[RunResult]:
    results: list[RunResult] = []
    for target in targets:
        cfg, model = llm_config.parse_target(target)
        if not cfg.api_key:
            console.print(f"[yellow]跳过 {target}：缺 {cfg.api_key_env}[/yellow]")
            continue

        console.print(f"\n[bold cyan]=== {target} ({model}) ===[/bold cyan]")
        for user_text, expected in cases:
            for r in range(rounds):
                tag = f"[{r + 1}/{rounds}]" if rounds > 1 else ""
                console.print(f"  {tag} {user_text!r}", end=" ")
                try:
                    text, elapsed, tokens = await call_target(target, user_text)
                    json_ok, intent, actual, score = score_plan(text, expected)
                    rate = tokens / elapsed if elapsed > 0 and tokens else 0
                    color = "green" if json_ok else "red"
                    console.print(
                        f"[{color}]{elapsed:.2f}s[/{color}] "
                        f"chars={len(text)} tok={tokens} {rate:.0f}t/s score={score}"
                    )
                    results.append(RunResult(
                        target=target,
                        user_text=user_text,
                        expected_steps=expected,
                        success=json_ok,
                        elapsed_sec=elapsed,
                        output_chars=len(text),
                        output_tokens=tokens,
                        json_valid=json_ok,
                        intent=intent,
                        actual_steps=actual,
                        quality_score=score,
                    ))
                except Exception as e:
                    console.print(f"[red]FAIL: {e}[/red]")
                    results.append(RunResult(
                        target=target,
                        user_text=user_text,
                        expected_steps=expected,
                        success=False,
                        elapsed_sec=0,
                        output_chars=0,
                        error=str(e)[:80],
                    ))
    return results


def summarize(results: list[RunResult]) -> None:
    """按 target 聚合"""
    by_target: dict[str, list[RunResult]] = {}
    for r in results:
        by_target.setdefault(r.target, []).append(r)

    table = Table(
        "target", "次数", "成功率", "平均延迟", "中位延迟",
        "平均 tok/s", "平均质量分", "备注",
        title="LLM Provider Benchmark",
    )
    rows: list[tuple] = []
    for target, rs in by_target.items():
        n = len(rs)
        ok = sum(1 for r in rs if r.success)
        success_rate = ok / n if n else 0
        latencies = [r.elapsed_sec for r in rs if r.success]
        avg_lat = statistics.mean(latencies) if latencies else 0
        med_lat = statistics.median(latencies) if latencies else 0
        rates = [
            r.output_tokens / r.elapsed_sec
            for r in rs
            if r.success and r.elapsed_sec and r.output_tokens
        ]
        avg_rate = statistics.mean(rates) if rates else 0
        scores = [r.quality_score for r in rs if r.success]
        avg_score = statistics.mean(scores) if scores else 0

        notes = []
        if any(r.error for r in rs):
            errs = [r.error for r in rs if r.error]
            notes.append(errs[0][:40])

        # 颜色
        rate_color = "green" if success_rate >= 0.9 else "yellow" if success_rate >= 0.5 else "red"
        lat_color = "green" if avg_lat < 2 else "yellow" if avg_lat < 5 else "red"
        score_color = "green" if avg_score >= 80 else "yellow" if avg_score >= 60 else "red"

        rows.append((
            target,
            str(n),
            f"[{rate_color}]{success_rate:.0%}[/{rate_color}]",
            f"[{lat_color}]{avg_lat:.2f}s[/{lat_color}]",
            f"{med_lat:.2f}s",
            f"{avg_rate:.0f}" if avg_rate else "-",
            f"[{score_color}]{avg_score:.1f}[/{score_color}]",
            " | ".join(notes) or "",
        ))

    # 按平均延迟排序
    rows.sort(key=lambda r: float(r[3].replace("[green]", "").replace("[/green]", "")
                                    .replace("[yellow]", "").replace("[/yellow]", "")
                                    .replace("[red]", "").replace("[/red]", "")
                                    .replace("s", "")) if "s" in r[3] else 999)
    for row in rows:
        table.add_row(*row)
    console.print()
    console.print(table)

    # 推荐
    console.print("\n[bold]路由建议：[/bold]")
    if not by_target:
        console.print("[red]没有可用 provider[/red]")
        return

    # 找延迟最短且质量 >= 70 的
    candidates = []
    for target, rs in by_target.items():
        latencies = [r.elapsed_sec for r in rs if r.success]
        scores = [r.quality_score for r in rs if r.success]
        if not latencies or not scores:
            continue
        avg_lat = statistics.mean(latencies)
        avg_score = statistics.mean(scores)
        if avg_score >= 70:
            candidates.append((target, avg_lat, avg_score))
    candidates.sort(key=lambda x: x[1])

    if candidates:
        console.print(f"  [green]最快+合格：[/green]{candidates[0][0]}")
        console.print(
            f"    config/llm.yaml → routing.task_planning.primary: {candidates[0][0]}"
        )
        if len(candidates) > 1:
            console.print(f"  [cyan]fallback 推荐：[/cyan]{candidates[1][0]}")
            console.print(
                f"    config/llm.yaml → routing.task_planning.fallback: {candidates[1][0]}"
            )


# ===== CLI =====

@click.command()
@click.option("--rounds", default=1, type=int, help="每个组合跑 N 次取平均")
@click.option(
    "--task",
    type=click.Choice(["simple", "medium", "complex", "all"]),
    default="all",
    help="测试用例分类",
)
@click.option(
    "--targets",
    default="deepseek.v4,deepseek.v4-pro,groq.llama70b,groq.llama8b,gemini.flash,gemini.flash-lite",
    help="逗号分隔的目标，对应 llm.yaml 里 'provider.alias'",
)
def main(rounds: int, task: str, targets: str) -> None:
    """LLM provider 基准测试"""
    target_list = [t.strip() for t in targets.split(",") if t.strip()]

    if task == "all":
        cases = TEST_CASES["simple"] + TEST_CASES["medium"] + TEST_CASES["complex"]
    else:
        cases = TEST_CASES[task]

    console.print(f"\n[bold]Targets:[/bold] {target_list}")
    console.print(f"[bold]Cases:[/bold] {len(cases)} 条 × {rounds} 轮")
    console.print(f"[dim]总调用：{len(target_list) * len(cases) * rounds} 次[/dim]\n")

    results = asyncio.run(run_benchmark(target_list, cases, rounds))
    summarize(results)


if __name__ == "__main__":
    main()
