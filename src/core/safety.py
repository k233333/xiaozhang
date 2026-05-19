"""高风险操作二次确认

由 actions/executor.py 在执行高风险 step 之前调用。
确认方式：keyboard / voice / both（来自 config.yaml）。
voice 模式 D6-7 阶段才接入；当前默认走 keyboard。
"""
from __future__ import annotations

import asyncio
import sys

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


def is_high_risk(action: str) -> bool:
    return action in settings.actions.high_risk_actions


async def confirm(action: str, detail: str = "") -> bool:
    """请求用户确认。返回 True 表示同意执行。"""
    if not settings.actions.high_risk_require_confirmation:
        return True
    if not is_high_risk(action):
        return True

    mode = settings.actions.confirmation_mode
    log.warning("高风险操作待确认", action=action, detail=detail, mode=mode)

    if mode in ("keyboard", "both"):
        return await _confirm_keyboard(action, detail)
    if mode == "voice":
        return await _confirm_voice(action, detail)
    log.error("未知确认模式", mode=mode)
    return False


async def _confirm_keyboard(action: str, detail: str) -> bool:
    """键盘确认：终端输入 y/n，10 秒超时默认 n"""
    prompt = f"\n⚠️  高风险操作 [{action}] {detail}\n输入 y 确认，其他取消（10 秒超时）: "
    try:
        loop = asyncio.get_running_loop()
        answer = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: input(prompt)),
            timeout=10.0,
        )
        return answer.strip().lower() in ("y", "yes", "是", "确定")
    except asyncio.TimeoutError:
        print("\n确认超时，已取消", file=sys.stderr)
        return False


async def _confirm_voice(action: str, detail: str) -> bool:
    """语音确认：D6-7 阶段实现"""
    log.warning("语音确认尚未实现，回退键盘", action=action)
    return await _confirm_keyboard(action, detail)
