"""A 级执行：Claude Vision 截图分析兜底

只在 C 级失败时调用。
让 Vision 模型看屏幕，给出"在 (x,y) 点击"或"输入 X"，再调用 D 级 pyautogui 完成。
"""
from __future__ import annotations

import asyncio

from src.brain.action_schema import Step
from src.core.logger import get_logger
from src.vision.vision_query import decide_from_screen

log = get_logger(__name__)


class StepResult:
    def __init__(self, success: bool, message: str = "") -> None:
        self.success = success
        self.message = message


async def execute(step: Step, *, last_failure: str = "") -> StepResult:
    intent = step.description or step.action
    log.info("A 级 Vision 兜底", intent=intent, last_failure=last_failure)
    decision = await decide_from_screen(intent=intent, last_failure=last_failure)
    if decision is None:
        return StepResult(False, "Vision 返回空")

    action = decision.get("action")
    if action == "click":
        return await _click_xy(int(decision.get("x", 0)), int(decision.get("y", 0)))
    if action == "type":
        return await _type_text(decision.get("text", ""))
    if action == "abort":
        return StepResult(False, decision.get("reason", "Vision 决定终止"))
    return StepResult(False, f"Vision 未知 action: {action}")


async def _click_xy(x: int, y: int) -> StepResult:
    if x <= 0 or y <= 0:
        return StepResult(False, "无效坐标")
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return StepResult(False, f"pyautogui 不可用: {e}")
    log.info("Vision 点击", x=x, y=y)
    await asyncio.get_running_loop().run_in_executor(
        None, lambda: pyautogui.click(x=x, y=y)
    )
    return StepResult(True)


async def _type_text(text: str) -> StepResult:
    from src.actions import tier_d_protocol  # noqa: PLC0415
    from src.brain.action_schema import Step as _Step  # noqa: PLC0415
    fake = _Step(tier="D", action="type", text=text)
    res = await tier_d_protocol.execute(fake)
    return StepResult(res.success, res.message)
