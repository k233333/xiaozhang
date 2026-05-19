"""状态机测试"""
from __future__ import annotations

import pytest

from src.core.state_machine import State, StateMachine


@pytest.mark.asyncio
async def test_initial_idle():
    sm = StateMachine()
    assert sm.state == State.IDLE


@pytest.mark.asyncio
async def test_valid_transitions():
    sm = StateMachine()
    assert await sm.transition(State.ARMED) is True
    assert sm.state == State.ARMED
    assert await sm.transition(State.LISTENING) is True
    assert await sm.transition(State.EXECUTING) is True
    assert await sm.transition(State.IDLE) is True


@pytest.mark.asyncio
async def test_invalid_transition_rejected():
    sm = StateMachine()
    # IDLE → EXECUTING 不合法（必须经过 LISTENING）
    ok = await sm.transition(State.EXECUTING)
    assert ok is False
    assert sm.state == State.IDLE


@pytest.mark.asyncio
async def test_force_transition_bypass():
    sm = StateMachine()
    ok = await sm.transition(State.EXECUTING, force=True)
    assert ok is True
    assert sm.state == State.EXECUTING


@pytest.mark.asyncio
async def test_listener_called():
    sm = StateMachine()
    seen = []

    def listener(old, new):
        seen.append((old, new))

    sm.add_listener(listener)
    await sm.transition(State.ARMED)
    assert (State.IDLE, State.ARMED) in seen


@pytest.mark.asyncio
async def test_async_listener():
    sm = StateMachine()
    seen = []

    async def alistener(old, new):
        seen.append((old, new))

    sm.add_listener(alistener)
    await sm.transition(State.ARMED)
    assert (State.IDLE, State.ARMED) in seen


@pytest.mark.asyncio
async def test_reset_to_idle():
    sm = StateMachine()
    await sm.transition(State.ARMED)
    await sm.reset()
    assert sm.state == State.IDLE
