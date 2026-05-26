"""运行时主流程（v4.0 — Claude Code 大脑 + 混合模式 + 自学习）

快速路径：本地 skill 匹配 → 直接执行（0.3s，不过 LLM）
慢速路径：转发 Claude Code → 自主规划+执行（5-15s）→ 成功后自动生成 SKILL.md
下次同样的任务 → 本地命中 → 0.3s

越用越快。

v4.0 变更：Hermes → Claude Code
  - CC 通过 headless 模式（claude --bare -p）调用
  - CC 自主决定是否调 xz.py 执行桌面操作
  - 比 Hermes 更智能（Claude/GPT-5.5 级别推理）
  - context 管理更好（不累积 session history）
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.actions.executor import PlanReport, execute_plan
from src.brain.action_schema import Plan
from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.learning import skill_stats
from src.memory import store
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
        # 快速路径 0：JSON skill 命中（视觉学习产出，0 token，<0.5s）
        # ============================================================
        try:
            from src.skills import json_skill as _json_skill  # noqa: PLC0415

            jhit = _json_skill.match(user_text)
            if jhit is not None:
                log.info("JSON skill 命中（视觉学习路径）", skill=jhit.name)
                store.add_event(session_id, "plan", "json_skill_hit", payload={"skill": jhit.name})

                ok, msg = _json_skill.execute(jhit)
                store.end_session(
                    session_id, intent=jhit.name, success=ok,
                    skill_hit=True, note=msg,
                )

                from src.brain.action_schema import Plan as _Plan, Step as _Step  # noqa: PLC0415

                stub_plan = _Plan(
                    intent=jhit.name, skill_hit=True, skill_name=jhit.name,
                    steps=[_Step(tier="D", action="json_skill", description=jhit.name)],
                    note=msg or "已执行",
                )
                return TurnResult(
                    user_text=user_text, plan=stub_plan, report=None,
                    skill_hit=True, success=ok,
                    note=msg or ("好的，已完成" if ok else "执行失败"),
                )
        except Exception as e:
            log.debug("JSON skill 路径异常（不影响）", err=str(e))

        # ============================================================
        # 快速路径 1：本地 SKILL.md 匹配（0.3s，不调 LLM）
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
        # 慢速路径：Claude Code 处理（5-15s）
        # ============================================================
        store.add_event(session_id, "route", "claude_code")
        log.info("本地未命中，转发 Claude Code", text=user_text[:50])

        from src.brain.cc_brain import chat as cc_chat  # noqa: PLC0415

        cc_result = await cc_chat(user_text)
        reply = cc_result.reply.strip()
        success = cc_result.success and bool(reply)

        log.info(
            "CC 回复",
            reply=reply[:100],
            success=success,
            cost=cc_result.cost_usd,
            cmds=cc_result.commands_executed,
        )
        store.add_event(session_id, "cc_reply", reply[:500], payload={
            "cost_usd": cc_result.cost_usd,
            "input_tokens": cc_result.input_tokens,
            "output_tokens": cc_result.output_tokens,
            "model": cc_result.model,
            "duration_sec": cc_result.duration_sec,
            "commands": cc_result.commands_executed,
        })

        # ============================================================
        # 自学习：CC 成功后尝试生成本地 SKILL.md
        # 下次同样的任务直接走快速路径
        # ============================================================
        if success:
            try:
                await _try_learn_skill(user_text, reply, session_id)
            except Exception as e:
                log.debug("skill 自学习失败（不影响）", err=str(e))

        store.end_session(
            session_id,
            intent="cc_dispatch",
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


async def _try_learn_skill(user_text: str, cc_reply: str, session_id: int) -> None:
    """CC 成功执行后，尝试生成本地 SKILL.md 供下次快速命中。

    防爆约束（避免巨量低质量 skill）：
      A. 必须是"操作类"任务（关键字白名单）
      B. user_text 长度 4-40 字（太短歧义大，太长是闲聊）
      C. 黑名单语义（取消/算了/几点/天气/你是谁）永不学
      D. 现有 skill 已能命中 → 不学
      E. 24h 冷却：同 intent slug 24h 内不学；超 24h 走 merge_triggers
    """
    import time as _time  # noqa: PLC0415
    from src.brain.action_schema import Plan, Step  # noqa: PLC0415
    from src.core.config import settings as _settings  # noqa: PLC0415
    from src.skills.generator import _slug, generate_skill, merge_triggers  # noqa: PLC0415

    # C. 黑名单语义
    BAD_KEYWORDS = (
        "取消", "停一下", "停止", "算了", "不要", "别了", "退出", "停下",
        "什么", "为什么", "怎么样", "好的", "知道了",
        "几点", "天气", "你是谁",
    )
    if any(bk in user_text for bk in BAD_KEYWORDS):
        log.debug("user_text 含黑名单语义，跳过学习", text=user_text[:30])
        return

    # B. 长度
    if len(user_text) < 4 or len(user_text) > 40:
        log.debug("user_text 长度不合适，跳过学习", length=len(user_text))
        return

    # A. 操作类 — CC 的回复中包含 xz.py 执行结果的标志
    action_keywords = [
        "xz.py", "[OK]", "已打开", "已执行", "已播放", "已搜索",
        "已启动", "已下载", "已发送", "已点击", "截图",
        "成功", "完成",
    ]
    if not any(kw in cc_reply for kw in action_keywords):
        log.debug("非操作类回复，跳过 skill 学习", reply=cc_reply[:50])
        return

    # D. 已能命中
    try:
        from src.skills import loader, matcher  # noqa: PLC0415
        existing = loader.load_all()
        if matcher.match(user_text, existing) is not None:
            log.debug("现有 skill 已能命中，跳过学习", text=user_text[:30])
            return
    except Exception:
        pass

    # E. 24h 冷却 + merge_triggers
    intent_slug = _slug(user_text[:30])
    target_dir = _settings.resolve_path(_settings.skills.generated_dir) / intent_slug
    target_md = target_dir / "SKILL.md"
    if target_md.exists():
        mtime = target_md.stat().st_mtime
        if _time.time() - mtime < 24 * 3600:
            log.debug("24h 内已学过同 intent，跳过", intent=intent_slug)
            return
        try:
            merged = merge_triggers(target_md, user_text)
            if merged:
                log.info("旧 skill 合并新 trigger", path=str(target_md), trigger=user_text)
                store.add_event(session_id, "skill_merged", str(target_md))
            return
        except Exception as e:
            log.debug("merge_triggers 失败", err=str(e))

    plan = Plan(
        intent=user_text[:30],
        skill_hit=False,
        steps=[Step(tier="D", action="run_cmd", cmd=["python", "xz.py", "run-turn", user_text])],
        note=cc_reply[:100],
    )

    path = await generate_skill(
        user_text=user_text,
        plan=plan,
        outcome="成功（由 Claude Code 执行）",
        overwrite=False,
    )
    if path:
        log.info("自学习：新 skill 已生成", path=str(path))
        store.add_event(session_id, "skill_learned", str(path))
