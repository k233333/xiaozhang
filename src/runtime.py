"""运行时主流程

封装"用户一句话 → 计划 → 执行 → 学习"的完整链路。
被 main.py 和 dev_console.py 共用。
"""
from __future__ import annotations

from dataclasses import dataclass

from src.actions.executor import PlanReport, execute_plan
from src.brain import llm_router
from src.brain.action_schema import Plan
from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.learning import skill_stats, workflow_recorder
from src.memory import recall, store
from src.skills import loader, matcher

log = get_logger(__name__)


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
    """处理一句用户输入。完整链路：路由 → 规划 → 执行 → 学习"""
    new_trace_id()

    user_text = (user_text or "").strip()
    if not user_text:
        return TurnResult(user_text, None, None, False, False, note="空输入")

    session_id = store.start_session(user_text=user_text)
    store.add_event(session_id, "transcript", user_text)

    if sm is not None:
        await sm.transition(State.EXECUTING)

    try:
        # 1. 路由：先查 skill
        skills = loader.load_all()
        hit = matcher.match(user_text, skills)
        plan: Plan | None = None
        skill_hit = False

        if hit is not None:
            log.info("命中 skill", skill=hit.name)
            plan = Plan(
                intent=hit.name,
                skill_hit=True,
                skill_name=hit.name,
                confirm_required=hit.confirm_required,
                steps=hit.steps,
                note=hit.description,
            )
            skill_hit = True
            store.add_event(session_id, "plan", "skill_hit", payload={"skill": hit.name})

        # 2. 没命中 → 调用 LLM 现规划
        if plan is None:
            ctx = recall.build_context(user_text)
            plan = await llm_router.plan(user_text, extra_context=ctx)
            if plan is None:
                store.end_session(session_id, success=False, note="planning_failed")
                if sm is not None:
                    await sm.reset()
                return TurnResult(user_text, None, None, False, False, note="LLM 规划失败")
            store.add_event(
                session_id,
                "plan",
                f"intent={plan.intent} steps={len(plan.steps)}",
                payload=plan.model_dump(exclude_none=True),
            )

        # 处理 ambiguous
        if plan.intent == "ambiguous":
            print(f"\n🤔 小张：{plan.note or '我没听清，能再说一次吗？'}")
            store.end_session(session_id, intent=plan.intent, success=False, note=plan.note)
            if sm is not None:
                await sm.reset()
            return TurnResult(user_text, plan, None, False, False, note=plan.note)

        # 3. 执行
        report = await execute_plan(plan, session_id=session_id)

        # 4. 学习 / 统计
        skill_stats.record(
            plan.skill_name if plan.skill_hit else None,
            success=report.all_succeeded(),
            user_text=user_text,
            failure_reason=report.aborted_reason,
        )

        if report.all_succeeded():
            await workflow_recorder.maybe_record(report, user_text=user_text)

        store.end_session(
            session_id,
            intent=plan.intent,
            success=report.all_succeeded(),
            skill_hit=plan.skill_hit,
            plan_json=plan.model_dump(exclude_none=True),
            note=plan.note,
        )

        return TurnResult(
            user_text=user_text,
            plan=plan,
            report=report,
            skill_hit=skill_hit,
            success=report.all_succeeded(),
            note=plan.note,
        )

    finally:
        if sm is not None:
            await sm.reset()
