"""运行时主流程（v3.1 — 混合模式 + 自学习）

快速路径：本地 skill 匹配 → 直接执行（0.3s，不过 Hermes）
慢速路径：转发 Hermes → LLM 规划+执行（4-8s）→ 成功后自动生成 SKILL.md
下次同样的任务 → 本地命中 → 0.3s

越用越快。
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from src.actions.executor import PlanReport, execute_plan
from src.brain.action_schema import Plan
from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.learning import skill_stats
from src.memory import store
from src.skills import loader, matcher

log = get_logger(__name__)

# Hermes agent 单例
_agent = None


def _get_agent():
    """获取或创建 Hermes AIAgent 单例（常驻内存）"""
    global _agent
    if _agent is not None:
        return _agent

    hermes_path = r"D:\11111begin\hermes-agent"
    if hermes_path not in sys.path:
        sys.path.insert(0, hermes_path)

    try:
        from run_agent import AIAgent

        _agent = AIAgent(
            model="deepseek-chat",
            quiet_mode=True,
            enabled_toolsets=["terminal", "skills"],
            max_iterations=30,
        )
        log.info("Hermes AIAgent 初始化完成")
        return _agent
    except Exception as e:
        log.error("Hermes AIAgent 初始化失败", err=str(e))
        return None


@dataclass
class TurnResult:
    """一轮交互的结果"""
    user_text: str
    plan: Plan | None
    report: PlanReport | None
    skill_hit: bool
    success: bool
    note: str = ""


async def run_turn(user_text: str, sm: StateMachine | None = None) -> TurnResult:
    """处理一句用户输入。

    快速路径：本地 skill 匹配 → 直接执行（0.3s）
    慢速路径：Hermes 处理（4-8s）→ 成功后自动学成 skill
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
        # ============================================================
        # 快速路径：本地 skill 匹配（0.3s，不调 LLM）
        # ============================================================
        skills = loader.load_all()
        hit = matcher.match(user_text, skills)

        if hit is not None:
            log.info("本地 skill 命中（快速路径）", skill=hit.name)
            plan = Plan(
                intent=hit.name,
                skill_hit=True,
                skill_name=hit.name,
                confirm_required=hit.confirm_required,
                steps=hit.steps,
                note=hit.description,
            )
            store.add_event(session_id, "plan", "skill_hit", payload={"skill": hit.name})

            report = await execute_plan(plan, session_id=session_id)

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
                note=plan.note or ("好的，已完成" if report.all_succeeded() else "执行失败"),
            )

        # ============================================================
        # 慢速路径：Hermes 处理（4-8s）
        # ============================================================
        store.add_event(session_id, "route", "hermes")
        log.info("本地未命中，转发 Hermes", text=user_text[:50])

        agent = _get_agent()
        if agent is None:
            store.end_session(session_id, success=False, note="Hermes 不可用")
            return TurnResult(
                user_text=user_text, plan=None, report=None,
                skill_hit=False, success=False,
                note="Hermes 初始化失败",
            )

        # Hermes 是同步的，放线程池
        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, agent.chat, user_text)
        reply = (reply or "").strip()
        success = bool(reply)

        log.info("Hermes 回复", reply=reply[:100], success=success)
        store.add_event(session_id, "hermes_reply", reply[:500])

        # ============================================================
        # 自学习：Hermes 成功后尝试生成本地 SKILL.md
        # 下次同样的任务直接走快速路径
        # ============================================================
        if success:
            try:
                await _try_learn_skill(user_text, reply, session_id)
            except Exception as e:
                log.debug("skill 自学习失败（不影响）", err=str(e))

        store.end_session(
            session_id,
            intent="hermes_dispatch",
            success=success,
            skill_hit=False,
            note=reply[:200],
        )

        return TurnResult(
            user_text=user_text, plan=None, report=None,
            skill_hit=False, success=success,
            note=reply or "已完成",
        )

    finally:
        if sm is not None:
            await sm.reset()


async def _try_learn_skill(user_text: str, hermes_reply: str, session_id: int) -> None:
    """Hermes 成功执行后，尝试生成本地 SKILL.md 供下次快速命中。

    只对"操作类"任务学习（打开app/搜索/系统控制），
    纯问答类（"现在几点"）不生成 skill。
    """
    from src.skills.generator import generate_skill  # noqa: PLC0415
    from src.brain.action_schema import Plan, Step  # noqa: PLC0415

    # 简单启发式：如果 Hermes 回复里提到了 xz.py 或执行了操作，才学习
    action_keywords = ["xz.py", "[OK]", "已打开", "已执行", "已播放", "已搜索", "已启动"]
    is_action = any(kw in hermes_reply for kw in action_keywords)

    if not is_action:
        log.debug("非操作类回复，跳过 skill 学习", reply=hermes_reply[:50])
        return

    # 构造一个最小 Plan 供 generator 使用
    plan = Plan(
        intent=user_text[:30],
        skill_hit=False,
        steps=[Step(tier="D", action="run_cmd", cmd=["python", "xz.py", "run-turn", user_text])],
        note=hermes_reply[:100],
    )

    path = await generate_skill(
        user_text=user_text,
        plan=plan,
        outcome="成功（由 Hermes 执行）",
        overwrite=False,
    )
    if path:
        log.info("自学习：新 skill 已生成", path=str(path))
        store.add_event(session_id, "skill_learned", str(path))
