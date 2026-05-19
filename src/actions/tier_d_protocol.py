"""D 级执行：URI Scheme / 快捷键 / 命令行 / 直接打开 URL

最低延迟、零成本。能用就用。
"""
from __future__ import annotations

import asyncio
import shlex
import subprocess
import time
import webbrowser
from typing import Any

from src.brain.action_schema import Step
from src.core.logger import get_logger

log = get_logger(__name__)


class StepResult:
    def __init__(self, success: bool, message: str = "", payload: Any = None) -> None:
        self.success = success
        self.message = message
        self.payload = payload

    def __repr__(self) -> str:
        return f"<StepResult success={self.success} msg={self.message!r}>"


async def execute(step: Step) -> StepResult:
    """执行 D 级步骤。失败返回 success=False，由上层降级。"""
    action = step.action
    handler = _HANDLERS.get(action)
    if handler is None:
        return StepResult(False, f"D 级不支持 action={action}")
    try:
        return await handler(step)
    except Exception as e:  # noqa: BLE001
        log.exception("D 级执行异常", action=action, err=str(e))
        return StepResult(False, f"D 级异常: {e}")


# ---------- 各 action 处理 ----------

async def _h_open_url(step: Step) -> StepResult:
    if not step.url:
        return StepResult(False, "缺少 url")
    log.info("打开 URL", url=step.url)
    # webbrowser.open 不阻塞
    ok = await asyncio.get_running_loop().run_in_executor(
        None, lambda: webbrowser.open(step.url, new=2)  # type: ignore[arg-type]
    )
    return StepResult(bool(ok), "" if ok else "webbrowser.open 返回 False")


async def _h_launch_app(step: Step) -> StepResult:
    """优先使用 url（uri scheme），其次 cmd"""
    if step.url:
        return await _h_open_url(step)
    if not step.cmd:
        return StepResult(False, "缺少 cmd 或 url")
    log.info("启动应用", cmd=step.cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *step.cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # 不等结束，启动即返回
        await asyncio.sleep(0.3)
        if proc.returncode is not None and proc.returncode != 0:
            return StepResult(False, f"返回码 {proc.returncode}")
        return StepResult(True)
    except FileNotFoundError as e:
        return StepResult(False, f"找不到可执行文件: {e}")


async def _h_keys(step: Step) -> StepResult:
    if not step.keys:
        return StepResult(False, "缺少 keys")
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return StepResult(False, f"pyautogui 不可用: {e}")

    keys = step.keys.lower().strip()
    log.info("发送快捷键", keys=keys)

    def _send():
        if "+" in keys:
            parts = [p.strip() for p in keys.split("+")]
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(keys)

    await asyncio.get_running_loop().run_in_executor(None, _send)
    return StepResult(True)


async def _h_type(step: Step) -> StepResult:
    if step.text is None:
        return StepResult(False, "缺少 text")
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return StepResult(False, f"pyautogui 不可用: {e}")
    log.info("输入文本", chars=len(step.text))

    def _type():
        # write 不支持中文，中文用剪贴板
        if any("\u4e00" <= ch <= "\u9fff" for ch in step.text):  # type: ignore[operator]
            try:
                import pyperclip  # noqa: PLC0415
                pyperclip.copy(step.text)
                pyautogui.hotkey("ctrl", "v")
                return
            except Exception:
                pass
        pyautogui.write(step.text, interval=0.02)  # type: ignore[arg-type]

    await asyncio.get_running_loop().run_in_executor(None, _type)
    return StepResult(True)


async def _h_wait(step: Step) -> StepResult:
    sec = max(0.0, float(step.timeout_seconds))
    log.info("等待", seconds=sec)
    await asyncio.sleep(sec)
    return StepResult(True)


async def _h_say(step: Step) -> StepResult:
    """小张反馈一句话。当前是 stdout 输出，未接入 TTS。"""
    text = step.text or step.description or ""
    print(f"\n🗣  小张：{text}")
    log.info("小张说", text=text)
    return StepResult(True)


async def _h_run_cmd(step: Step) -> StepResult:
    """通用 shell 执行（debug 用，慎用）"""
    if not step.cmd:
        return StepResult(False, "缺少 cmd")
    log.info("运行命令", cmd=step.cmd)
    proc = await asyncio.create_subprocess_exec(
        *step.cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(), timeout=step.timeout_seconds
        )
    except asyncio.TimeoutError:
        proc.kill()
        return StepResult(False, "命令超时")
    if proc.returncode != 0:
        return StepResult(False, f"返回码 {proc.returncode}: {err.decode(errors='ignore')[:200]}")
    return StepResult(True, payload=out.decode(errors="ignore")[:500])


_HANDLERS = {
    "open_url": _h_open_url,
    "launch_app": _h_launch_app,
    "keys": _h_keys,
    "type": _h_type,
    "wait": _h_wait,
    "say": _h_say,
    "run_cmd": _h_run_cmd,
}
