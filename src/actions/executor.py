"""三级降级调度器

接收 Plan，逐步执行：
  按 step.tier 选 D/C/A
  失败则按 fallback_tier 降级
  D → C → A → 上报失败
高风险 step 在执行前调用 safety.confirm()。
每步执行前可选截图（config.actions.screenshot_before_each_step）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.actions import tier_a_vision, tier_c_uia, tier_d_protocol
from src.brain.action_schema import Plan, Step, Tier
from src.core.config import settings
from src.core.logger import get_logger
from src.core.safety import confirm
from src.memory import store
from src.vision.screenshot import grab_full

log = get_logger(__name__)


_TIER_ORDER: list[Tier] = ["D", "C", "A"]


@dataclass
class StepReport:
    step: Step
    final_tier: Tier
    success: bool
    message: str = ""
    elapsed_sec: float = 0.0
    fallback_chain: list[str] = field(default_factory=list)


@dataclass
class PlanReport:
    plan: Plan
    success: bool
    steps: list[StepReport] = field(default_factory=list)
    aborted_reason: str = ""

    def all_succeeded(self) -> bool:
        return self.success and all(s.success for s in self.steps)


def _next_tier(current: Tier, fallback: Tier | None) -> Tier | None:
    """决定下一级降级目标"""
    if fallback is not None and fallback != current:
        return fallback
    idx = _TIER_ORDER.index(current)
    if idx + 1 < len(_TIER_ORDER):
        return _TIER_ORDER[idx + 1]
    return None


async def _exec_one_tier(step: Step, tier: Tier, last_msg: str = "") -> tuple[bool, str]:
    log.info("执行步骤", tier=tier, action=step.action, desc=step.description)

    if tier == "D":
        r = await tier_d_protocol.execute(step)
        return r.success, r.message
    if tier == "C":
        r = await tier_c_uia.execute(step)
        return r.success, r.message
    if tier == "A":
        r = await tier_a_vision.execute(step, last_failure=last_msg)
        return r.success, r.message
    return False, f"未知 tier: {tier}"


async def execute_step(step: Step, session_id: int | None = None) -> StepReport:
    """执行单个 step。带降级。"""
    # 二次确认
    if step.requires_confirmation:
        ok = await confirm(step.action, step.description or "")
        if not ok:
            return StepReport(step=step, final_tier=step.tier, success=False, message="用户拒绝")

    if settings.actions.screenshot_before_each_step:
        try:
            grab_full(save=True, tag=f"before_{step.action}")
        except Exception as e:  # noqa: BLE001
            log.debug("截图失败（可忽略）", err=str(e))

    chain: list[str] = []
    current: Tier | None = step.tier
    last_msg = ""
    success = False

    t0 = time.monotonic()
    while current is not None:
        chain.append(current)
        if session_id is not None:
            store.add_event(
                session_id,
                "step_start",
                f"[{current}] {step.action}",
                payload=step.model_dump(exclude_none=True),
            )
        ok, msg = await _exec_one_tier(step, current, last_msg=last_msg)
        last_msg = msg
        if session_id is not None:
            store.add_event(
                session_id,
                "step_end",
                f"[{current}] {step.action} -> {'OK' if ok else 'FAIL'}",
                payload={"tier": current, "success": ok, "message": msg},
            )
        if ok:
            success = True
            break
        # 降级
        nxt = _next_tier(current, step.fallback_tier if current == step.tier else None)
        if nxt == current:
            break
        current = nxt

    elapsed = time.monotonic() - t0
    return StepReport(
        step=step,
        final_tier=chain[-1] if chain else step.tier,  # type: ignore[arg-type]
        success=success,
        message=last_msg,
        elapsed_sec=elapsed,
        fallback_chain=chain,
    )


async def execute_plan(plan: Plan, *, session_id: int | None = None) -> PlanReport:
    """执行整个 plan。任一步失败则后续不执行。"""
    report = PlanReport(plan=plan, success=True)

    if plan.intent == "ambiguous":
        log.info("意图模糊，不执行", note=plan.note)
        report.success = False
        report.aborted_reason = "ambiguous"
        return report

    for step in plan.steps:
        sr = await execute_step(step, session_id=session_id)
        report.steps.append(sr)
        if not sr.success:
            report.success = False
            report.aborted_reason = sr.message
            log.warning("步骤失败，终止后续", message=sr.message)
            break

    log.info("plan 执行完成", success=report.success, steps=len(report.steps))
    return report
