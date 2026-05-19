"""系统托盘图标

颜色映射：
  IDLE       -> 灰
  ARMED      -> 黄
  LISTENING  -> 绿
  EXECUTING  -> 蓝
  ERROR      -> 红

托盘菜单：
  - 状态显示
  - 重置（强制回 IDLE）
  - 退出
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from src.core.logger import get_logger
from src.core.state_machine import State

if TYPE_CHECKING:
    from src.core.state_machine import StateMachine

log = get_logger(__name__)


_COLORS: dict[State, tuple[int, int, int]] = {
    State.IDLE: (128, 128, 128),
    State.ARMED: (255, 200, 0),
    State.LISTENING: (0, 200, 80),
    State.EXECUTING: (0, 150, 230),
    State.ERROR: (220, 60, 60),
}


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=color + (255,))
    return img


class TrayManager:
    def __init__(self, sm: "StateMachine") -> None:
        self.sm = sm
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _build(self) -> pystray.Icon:
        def on_reset(icon, item):  # noqa: ARG001
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            loop.run_until_complete(self.sm.reset())

        def on_quit(icon, item):  # noqa: ARG001
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem(lambda item: f"状态：{self.sm.state.value}", None, enabled=False),
            pystray.MenuItem("重置", on_reset),
            pystray.MenuItem("退出", on_quit),
        )
        icon = pystray.Icon(
            "xiaozhang",
            _make_icon(_COLORS[self.sm.state]),
            "小张",
            menu,
        )
        return icon

    def update_state_icon(self, state: State) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = _make_icon(_COLORS.get(state, (128, 128, 128)))
            self._icon.title = f"小张 · {state.value}"
        except Exception as e:  # noqa: BLE001
            log.debug("更新托盘图标失败", err=str(e))

    def start(self) -> None:
        if self._thread is not None:
            return
        self._icon = self._build()

        def _run():
            try:
                self._icon.run()
            except Exception as e:  # noqa: BLE001
                log.warning("托盘退出", err=str(e))

        self._thread = threading.Thread(target=_run, daemon=True, name="tray")
        self._thread.start()
        log.info("托盘已启动")

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
