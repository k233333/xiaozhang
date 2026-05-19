"""executor 三级降级测试

模拟某 step 在 D 级失败 → 自动降级 C → 再降 A。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.actions import executor
from src.brain.action_schema import Plan, Step


class _MockResult:
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


@pytest.mark.asyncio
async def test_d_success_no_downgrade():
    s = Step(tier="D", action="open_url", url="https://x.com")
    with patch("src.actions.executor.tier_d_protocol.execute",
               new=AsyncMock(return_value=_MockResult(True))):
        report = await executor.execute_step(s)
    assert report.success is True
    assert report.fallback_chain == ["D"]


@pytest.mark.asyncio
async def test_d_fail_downgrade_to_c():
    s = Step(tier="D", action="click", target={"name": "OK"}, fallback_tier="C")
    with (
        patch("src.actions.executor.tier_d_protocol.execute",
              new=AsyncMock(return_value=_MockResult(False, "D 不支持"))),
        patch("src.actions.executor.tier_c_uia.execute",
              new=AsyncMock(return_value=_MockResult(True))),
    ):
        report = await executor.execute_step(s)
    assert report.success is True
    assert report.fallback_chain == ["D", "C"]


@pytest.mark.asyncio
async def test_d_c_fail_downgrade_to_a():
    s = Step(tier="D", action="click", target={"name": "OK"})
    with (
        patch("src.actions.executor.tier_d_protocol.execute",
              new=AsyncMock(return_value=_MockResult(False, "x"))),
        patch("src.actions.executor.tier_c_uia.execute",
              new=AsyncMock(return_value=_MockResult(False, "y"))),
        patch("src.actions.executor.tier_a_vision.execute",
              new=AsyncMock(return_value=_MockResult(True))),
    ):
        report = await executor.execute_step(s)
    assert report.success is True
    # D → C → A 全走完
    assert report.fallback_chain == ["D", "C", "A"]


@pytest.mark.asyncio
async def test_all_tiers_fail():
    s = Step(tier="D", action="click", target={"name": "x"})
    with (
        patch("src.actions.executor.tier_d_protocol.execute",
              new=AsyncMock(return_value=_MockResult(False, "1"))),
        patch("src.actions.executor.tier_c_uia.execute",
              new=AsyncMock(return_value=_MockResult(False, "2"))),
        patch("src.actions.executor.tier_a_vision.execute",
              new=AsyncMock(return_value=_MockResult(False, "3"))),
    ):
        report = await executor.execute_step(s)
    assert report.success is False
    assert "D" in report.fallback_chain
    assert "A" in report.fallback_chain


@pytest.mark.asyncio
async def test_plan_with_first_step_failure_aborts():
    plan = Plan(intent="x", steps=[
        Step(tier="D", action="open_url", url="https://x.com"),
        Step(tier="D", action="open_url", url="https://y.com"),
    ])
    call_count = {"v": 0}

    async def fake_d(step):
        call_count["v"] += 1
        return _MockResult(False)

    with (
        patch("src.actions.executor.tier_d_protocol.execute", new=AsyncMock(side_effect=fake_d)),
        patch("src.actions.executor.tier_c_uia.execute",
              new=AsyncMock(return_value=_MockResult(False))),
        patch("src.actions.executor.tier_a_vision.execute",
              new=AsyncMock(return_value=_MockResult(False))),
    ):
        report = await executor.execute_plan(plan)
    assert report.success is False
    assert len(report.steps) == 1  # 第一步失败后不应执行第二步
