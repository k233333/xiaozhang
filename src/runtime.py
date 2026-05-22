"""运行时主流程（v3.0 — Hermes 作为大脑）

小张进程只负责：
  1. 本地 skill 快速匹配（0.3s，命中直接执行）
  2. 没命中 → 转发给 Hermes（LLM 规划由 Hermes 完成）

不再直接调用 LLM API。
"""
from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass

from src.actions.executor import PlanReport, execute_plan
from src.brain.action_schema import Plan
from src.core.config import settings
from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.learning import skill_stats
from src.memory import store
from src.skills import loader, matcher

log = get_logger(__name__)

# Hermes 可执行文件路径
_HERMES_EXE = r"D:\11111begin\hermes-agent\venv\Scripts\hermes.exe"


@dataclass
class TurnResult:
    """一轮交互的结果"""

    user_text: str
    plan: Plan | None
    report: PlanReport | None
    skill_hit: bool
    success: bool
    note: str = ""


async def _call_hermes(user_text: str) -> tuple[bool, str]:
    """调用 Hermes oneshot 模式处理用户请求。

    返回 (success, reply_text)。
    """
    log.info("转发给 Hermes", text=user_text[:50])
    try:
        proc = await asyncio.create_subprocess_exec(
            _HERMES_EXE, "chat", "-q", user_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=r"D:\11111begin\xiaozhang",
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode("utf-8", errors="replace").strip()

        if proc.returncode == 0:
            # 提取 Hermes 的最后回复（通常是最后几行）
            lines = output.splitlines()
            # Hermes 输出可能包含工具调用日志，取最后的非空行作为回复
            reply = ""
            for line in reversed(lines):
                line = line.strip()
                if line and not line.startswith("[") and not line.startswith("─"):
                    reply = line
                    break
            if not reply:
                reply = "好的，已完成"
            log.info("Hermes 返回", reply=reply[:80], exit_code=0)
            return True, reply
        else:
            err = stderr.decode("utf-8", errors="replace").strip()[:200]
            log.warning("Hermes 执行失败", exit_code=proc.returncode, err=err)
            return False, f"Hermes 执行失败: {err or output[:100]}"

    except asyncio.TimeoutError:
        log.warning("Hermes 超时（60s）")
        return False, "Hermes 处理超时"
    except FileNotFoundError:
        log.error("Hermes 可执行文件不存在", path=_HERMES_EXE)
        return False, "Hermes 未安装"
    except Exception as e:
        log.exception("Hermes 调用异常", err=str(e))
        return False, f"Hermes 异常: {e}"


async def run_turn(user_text: str, sm: StateMachine | None = None) -> TurnResult:
    """处理一句用户输入。

    快速路径：本地 skill 匹配 → 直接执行（0.3s）
    慢速路径：转发 Hermes → Hermes 规划+执行（3-30s）
    """
    new_trace_id()

    user_text = (user_text or "").strip()
    if not user_text:
        return TurnResult(user_text, None, None, False, False, note="空输入")

    session_id = store.start_session(user_text=user_text)
    store.add_event(session_id, "transcript", user_text)

    if sm is not None:
        await sm.transition(State.EXECUTING)

    try:
        # 1. 本地 skill 快速匹配（0 LLM 调用，0.3s）
        skills = loader.load_all()
        hit = matcher.match(user_text, skills)

        if hit is not None:
            log.info("命中 skill（本地快速路径）", skill=hit.name)
            plan = Plan(
                intent=hit.name,
                skill_hit=True,
                skill_name=hit.name,
                confirm_required=hit.confirm_required,
                steps=hit.steps,
                note=hit.description,
            )
            store.add_event(session_id, "plan", "skill_hit", payload={"skill": hit.name})

            # 执行
            report = await execute_plan(plan, session_id=session_id)

            # 统计
            skill_stats.record(
                hit.name,
                success=report.all_succeeded(),
                user_text=user_text,
                failure_reason=report.aborted_reason,
            )

            store.end_session(
                session_id,
                intent=plan.intent,
                success=report.all_succeeded(),
                skill_hit=True,
                plan_json=plan.model_dump(exclude_none=True),
                note=plan.note,
            )

            return TurnResult(
                user_text=user_text,
                plan=plan,
                report=report,
                skill_hit=True,
                success=report.all_succeeded(),
                note=plan.note,
            )

        # 2. 没命中 → 转发给 Hermes（大脑）
        store.add_event(session_id, "route", "hermes")
        success, reply = await _call_hermes(user_text)

        store.end_session(
            session_id,
            intent="hermes_dispatch",
            success=success,
            skill_hit=False,
            note=reply,
        )

        return TurnResult(
            user_text=user_text,
            plan=None,
            report=None,
            skill_hit=False,
            success=success,
            note=reply,
        )

    finally:
        if sm is not None:
            await sm.reset()
