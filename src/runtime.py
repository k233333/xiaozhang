"""运行时主流程

封装"用户一句话 → 计划 → 执行 → 学习"的完整链路。
被 main.py 和 dev_console.py 共用。
"""
from __future__ import annotations

from dataclasses import dataclass

from src.actions.executor import PlanReport, execute_plan
from src.brain import llm_router
from src.brain.action_schema import Plan, Step
from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.learning import skill_stats, workflow_recorder
from src.memory import recall, store
from src.skills import loader, matcher
from src.skills.matcher import match_with_trigger

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


_INTENT_PREFIXES = (
    "我想看", "想看", "看看", "帮我搜",
    "在抖音搜", "抖音搜", "打开抖音搜", "抖音找", "看抖音的", "搜抖音",
    "在b站搜", "b站搜", "bilibili搜",
    "搜索", "帮我找", "找一下",
)


def _extract_search_arg(user_text: str, trigger: str) -> str:
    """从用户原文或 trigger 中提取搜索关键词，剔除意图前缀。

    优先从 user_text 提取（更完整），再从 trigger 提取。
    "我想看不惑兄弟" → "不惑兄弟"
    "在抖音搜李子柒最新视频" → "李子柒最新视频"
    """
    for src in (user_text, trigger):
        for prefix in sorted(_INTENT_PREFIXES, key=len, reverse=True):  # 长前缀优先
            if src.startswith(prefix):
                rest = src[len(prefix):].strip()
                if rest:
                    return rest
    # 无法剥离 → 用 trigger 本身（短 trigger 本来就是关键词，如"不惑兄弟"）
    return trigger


def _inject_keyword(steps: list[Step], keyword: str) -> list[Step]:
    """把 steps 里所有 text='{KEYWORD}' 替换为实际关键词。返回新的 Step 列表。"""
    if not keyword:
        return steps
    result = []
    for s in steps:
        if s.text and "{KEYWORD}" in s.text:
            s = s.model_copy(update={"text": s.text.replace("{KEYWORD}", keyword)})
        result.append(s)
    return result


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
        # 1. 路由：先查 skill（返回命中的 trigger 词，用于 {KEYWORD} 注入）
        skills = loader.load_all()
        match_info = match_with_trigger(user_text, skills)
        plan: Plan | None = None
        skill_hit = False

        if match_info is not None:
            hit = match_info.skill
            # 若 skill 有 argument-hint，从用户原文中剥离意图前缀提取实际关键词
            # 否则直接用 trigger（对于"不惑兄弟"这种纯关键词 trigger 也正确）
            has_arg_hint = bool(hit.frontmatter.get("argument-hint"))
            keyword = (
                _extract_search_arg(user_text, match_info.trigger)
                if has_arg_hint
                else match_info.trigger
            )
            log.info("命中 skill", skill=hit.name, trigger=match_info.trigger,
                     keyword=keyword, method=match_info.method)

            # 将 steps 中的 {KEYWORD} 占位替换为实际关键词
            injected_steps = _inject_keyword(hit.steps, keyword)

            plan = Plan(
                intent=hit.name,
                skill_hit=True,
                skill_name=hit.name,
                confirm_required=hit.confirm_required,
                steps=injected_steps,
                note=hit.description,
            )
            skill_hit = True
            store.add_event(session_id, "plan", "skill_hit", payload={"skill": hit.name, "keyword": keyword})

        # 2. 没命中 → 意图复杂度预判 + 调用 LLM 现规划
        if plan is None:
            from src.brain.intent_classifier import Complexity, classify  # noqa: PLC0415

            complexity = classify(user_text)
            use_complex = complexity == Complexity.COMPLEX
            if use_complex:
                log.info("意图分类器判定为复杂任务，直接走 v4-pro", text=user_text[:30])

            ctx = recall.build_context(user_text)
            plan = await llm_router.plan(user_text, extra_context=ctx, complex=use_complex)
            if plan is None:
                store.end_session(session_id, success=False, note="planning_failed")
                if sm is not None:
                    await sm.reset()
                return TurnResult(user_text, None, None, False, False, note="LLM 规划失败")

            # LLM 自我标记需要复杂推理 → 用 v4-pro 重新规划（仅在非 complex 路径时 escalate）
            if not use_complex and getattr(plan, "needs_complex_reasoning", False):
                log.info("LLM 自标 needs_complex_reasoning，escalate 到 v4-pro", intent=plan.intent)
                store.add_event(session_id, "escalate", "v4-pro", payload={"intent": plan.intent})
                escalated = await llm_router.plan(user_text, extra_context=ctx, complex=True)
                if escalated is not None:
                    plan = escalated
                else:
                    log.warning("escalate 失败，沿用 v4 的规划")

            store.add_event(
                session_id,
                "plan",
                f"intent={plan.intent} steps={len(plan.steps)}",
                payload=plan.model_dump(exclude_none=True),
            )

        # 处理 ambiguous
        if plan.intent == "ambiguous":
            print(f"\n[小张] {plan.note or '我没听清，能再说一次吗？'}")
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
