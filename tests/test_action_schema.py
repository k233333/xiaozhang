"""Action schema 校验测试"""
from __future__ import annotations

import pytest

from src.brain.action_schema import Plan, Step


def test_step_minimal_d_open_url():
    s = Step(tier="D", action="open_url", url="https://x.com")
    assert s.tier == "D"
    assert s.action == "open_url"
    assert s.timeout_seconds == 10.0


def test_step_invalid_tier():
    with pytest.raises(Exception):  # pydantic ValidationError
        Step(tier="X", action="foo")


def test_plan_valid_minimal():
    p = Plan(intent="test", steps=[Step(tier="D", action="open_url", url="https://x.com")])
    assert p.intent == "test"
    assert p.skill_hit is False
    assert len(p.steps) == 1


def test_plan_from_dict():
    raw = {
        "intent": "watch_x",
        "steps": [
            {"tier": "D", "action": "open_url", "url": "https://x.com"},
            {"tier": "C", "action": "click", "target": {"name": "OK"}},
        ],
    }
    p = Plan.from_dict(raw)
    assert p.intent == "watch_x"
    assert len(p.steps) == 2
    assert p.steps[0].tier == "D"
    assert p.steps[1].tier == "C"


def test_plan_with_high_risk_step():
    raw = {
        "intent": "send",
        "steps": [
            {"tier": "C", "action": "send_message", "text": "hi", "requires_confirmation": True}
        ],
    }
    p = Plan.from_dict(raw)
    assert p.steps[0].requires_confirmation is True


def test_plan_ambiguous():
    p = Plan.from_dict({"intent": "ambiguous", "note": "你说哪个？"})
    assert p.intent == "ambiguous"
    assert len(p.steps) == 0


def test_plan_with_fallback_tier():
    p = Plan.from_dict({
        "intent": "x",
        "steps": [{"tier": "D", "action": "open_url", "url": "x", "fallback_tier": "C"}],
    })
    assert p.steps[0].fallback_tier == "C"
