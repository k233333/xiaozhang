# coding: utf-8
"""底层确定性点击 / 键盘 / 滚动 — 全部 0 token，不过 LLM。"""
from __future__ import annotations

import time

from src.core.logger import get_logger

log = get_logger(__name__)


def _ensure_dpi_aware() -> None:
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def click_xy(x: int, y: int, *, button: str = "left", clicks: int = 1) -> bool:
    _ensure_dpi_aware()
    if x < 0 or y < 0:
        log.warning("无效坐标", x=x, y=y)
        return False
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:
        log.warning("pyautogui 不可用", err=str(e))
        return False
    log.info("click_xy", x=x, y=y, button=button, clicks=clicks)
    try:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        return True
    except Exception as e:
        log.warning("click_xy 失败", err=str(e))
        return False


def double_click_xy(x: int, y: int) -> bool:
    return click_xy(x, y, clicks=2)


def type_text(text: str, *, interval: float = 0.02) -> bool:
    if not text:
        return True
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:
        log.warning("pyautogui 不可用", err=str(e))
        return False
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    if has_cjk:
        try:
            import pyperclip  # noqa: PLC0415
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return True
        except Exception as e:
            log.warning("剪贴板注入失败", err=str(e))
    try:
        pyautogui.write(text, interval=interval)
        return True
    except Exception as e:
        log.warning("type_text 失败", err=str(e))
        return False


def hotkey(keys: str) -> bool:
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as e:
        log.warning("pyautogui 不可用", err=str(e))
        return False
    keys = keys.lower().strip()
    try:
        if "+" in keys:
            parts = [p.strip() for p in keys.split("+")]
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(keys)
        return True
    except Exception as e:
        log.warning("hotkey 失败", err=str(e))
        return False


def wait(seconds: float) -> None:
    time.sleep(max(0.0, seconds))
