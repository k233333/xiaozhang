"""D 级 action 测试（不真的开浏览器/启程序，只看分支）"""
from __future__ import annotations

import pytest

from src.actions import tier_d_protocol
from src.brain.action_schema import Step


@pytest.mark.asyncio
async def test_unknown_action_returns_failure():
    s = Step(tier="D", action="this_action_doesnt_exist")
    r = await tier_d_protocol.execute(s)
    assert r.success is False
    assert "不支持" in r.message


@pytest.mark.asyncio
async def test_open_url_missing_url():
    s = Step(tier="D", action="open_url")
    r = await tier_d_protocol.execute(s)
    assert r.success is False


@pytest.mark.asyncio
async def test_keys_missing_keys():
    s = Step(tier="D", action="keys")
    r = await tier_d_protocol.execute(s)
    assert r.success is False


@pytest.mark.asyncio
async def test_type_missing_text():
    s = Step(tier="D", action="type")
    r = await tier_d_protocol.execute(s)
    assert r.success is False


@pytest.mark.asyncio
async def test_wait_works():
    s = Step(tier="D", action="wait", timeout_seconds=0.05)
    r = await tier_d_protocol.execute(s)
    assert r.success is True


@pytest.mark.asyncio
async def test_say_works():
    s = Step(tier="D", action="say", text="测试一下")
    r = await tier_d_protocol.execute(s)
    assert r.success is True


@pytest.mark.asyncio
async def test_launch_app_missing_args():
    s = Step(tier="D", action="launch_app")
    r = await tier_d_protocol.execute(s)
    assert r.success is False
