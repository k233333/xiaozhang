"""高风险确认机制测试"""
from __future__ import annotations

import pytest

from src.core.safety import is_high_risk


def test_high_risk_actions():
    assert is_high_risk("delete_file") is True
    assert is_high_risk("send_message") is True
    assert is_high_risk("shutdown") is True


def test_low_risk_actions():
    assert is_high_risk("open_url") is False
    assert is_high_risk("launch_app") is False
    assert is_high_risk("keys") is False
    assert is_high_risk("type") is False


def test_unknown_action_treated_low_risk():
    assert is_high_risk("totally_unknown_action") is False


@pytest.mark.asyncio
async def test_confirm_low_risk_action_auto_pass():
    """低风险动作不需要确认，直接 True"""
    from src.core.safety import confirm

    ok = await confirm("open_url", "https://x.com")
    assert ok is True
