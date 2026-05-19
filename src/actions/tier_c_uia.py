"""C 级执行：UIAutomation 控件树 / DOM selector

只在 D 级失败时调用。Windows 平台用 pywinauto + uiautomation。
网页相关用 Playwright（可选依赖，未装则降级）。
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from src.brain.action_schema import Step
from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


class StepResult:
    def __init__(self, success: bool, message: str = "", payload: Any = None) -> None:
        self.success = success
        self.message = message
        self.payload = payload


async def execute(step: Step) -> StepResult:
    if sys.platform != "win32":
        return StepResult(False, "C 级（UIA）目前只在 Windows 实现")
    handler = _HANDLERS.get(step.action)
    if handler is None:
        return StepResult(False, f"C 级不支持 action={step.action}")
    try:
        return await asyncio.wait_for(handler(step), timeout=step.timeout_seconds)
    except asyncio.TimeoutError:
        return StepResult(False, f"C 级超时 {step.timeout_seconds}s")
    except Exception as e:  # noqa: BLE001
        log.exception("C 级执行异常", action=step.action, err=str(e))
        return StepResult(False, f"C 级异常: {e}")


async def _h_click(step: Step) -> StepResult:
    if not step.target:
        return StepResult(False, "缺少 target")
    log.info("UIA click", target=step.target)

    def _do_click() -> tuple[bool, str]:
        try:
            import uiautomation as auto  # noqa: PLC0415
        except Exception as e:  # noqa: BLE001
            return False, f"uiautomation 不可用: {e}"

        target = step.target or {}
        # 在桌面树里查
        ctrl = None
        if target.get("automation_id"):
            ctrl = auto.Control(searchDepth=20, AutomationId=target["automation_id"])
        elif target.get("name"):
            kwargs: dict[str, Any] = {"Name": target["name"]}
            if target.get("control_type"):
                kwargs["ControlType"] = _control_type(target["control_type"])
            ctrl = auto.Control(searchDepth=20, **kwargs)

        if ctrl is None or not ctrl.Exists(maxSearchSeconds=settings.actions.automation_timeout_seconds):
            return False, "目标控件未找到"
        try:
            ctrl.Click(simulateMove=False)
            return True, ""
        except Exception as e:  # noqa: BLE001
            return False, f"点击失败: {e}"

    ok, msg = await asyncio.get_running_loop().run_in_executor(None, _do_click)
    return StepResult(ok, msg)


def _control_type(name: str) -> int:
    """把字符串转成 uiautomation.ControlType.* 数值"""
    try:
        import uiautomation as auto  # noqa: PLC0415
    except Exception:
        return 0
    val = getattr(auto.ControlType, f"{name}Control", None)
    if val is not None:
        return val
    val = getattr(auto.ControlType, name, None)
    if val is not None:
        return val
    log.warning("未知 control_type，回退 None", name=name)
    return 0


async def _h_type(step: Step) -> StepResult:
    """C 级 type：先聚焦目标再输入"""
    if step.target:
        click_res = await _h_click(step)
        if not click_res.success:
            return click_res
        await asyncio.sleep(0.1)
    # 沿用 D 级 type 实现
    from src.actions import tier_d_protocol  # noqa: PLC0415
    res = await tier_d_protocol._h_type(step)
    return StepResult(res.success, res.message)


_HANDLERS = {
    "click": _h_click,
    "type": _h_type,
}
