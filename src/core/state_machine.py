"""状态机

IDLE → ARMED → LISTENING → EXECUTING → IDLE

由 main.py 持有一个 StateMachine 实例，各模块通过 transition() 修改状态。
状态变化时触发 listeners（用于托盘灯色 / 提示音 / 日志）。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum

from src.core.logger import get_logger

log = get_logger(__name__)


class State(str, Enum):
    IDLE = "idle"           # 持续监听唤醒词，CPU < 1%
    ARMED = "armed"         # 听到第一段，4 秒窗口等第二段
    LISTENING = "listening" # 录音中
    EXECUTING = "executing" # LLM 规划 + 自动化执行
    ERROR = "error"


# 合法状态转移
_VALID_TRANSITIONS: dict[State, set[State]] = {
    State.IDLE: {State.ARMED, State.LISTENING, State.ERROR},  # LISTENING：手动 push-to-talk
    State.ARMED: {State.IDLE, State.LISTENING, State.ERROR},
    State.LISTENING: {State.EXECUTING, State.IDLE, State.ERROR},
    State.EXECUTING: {State.IDLE, State.ERROR},
    State.ERROR: {State.IDLE},
}


Listener = Callable[[State, State], Awaitable[None] | None]


class StateMachine:
    def __init__(self, initial: State = State.IDLE) -> None:
        self._state: State = initial
        self._lock = asyncio.Lock()
        self._listeners: list[Listener] = []

    @property
    def state(self) -> State:
        return self._state

    def add_listener(self, fn: Listener) -> None:
        self._listeners.append(fn)

    async def transition(self, target: State, *, force: bool = False) -> bool:
        """转移到目标状态。非法转移返回 False（除非 force=True）。"""
        async with self._lock:
            current = self._state
            if not force and target not in _VALID_TRANSITIONS.get(current, set()) and target != current:
                log.warning("非法状态转移", current=current.value, target=target.value)
                return False
            if target == current:
                return True
            self._state = target
            log.info("状态转移", from_=current.value, to=target.value)
            # 触发 listeners
            for fn in self._listeners:
                try:
                    res = fn(current, target)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    log.exception("listener 异常", err=str(e))
            return True

    async def reset(self) -> None:
        await self.transition(State.IDLE, force=True)
