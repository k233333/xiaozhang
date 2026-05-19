"""cpu_guard 测试"""
from __future__ import annotations

from src.core import cpu_guard


def test_cpu_load_pct_returns_float():
    v = cpu_guard.cpu_load_pct(0.0)
    assert isinstance(v, float)
    assert 0 <= v <= 100


def test_memory_pressure_shape():
    mp = cpu_guard.memory_pressure()
    assert "total_gb" in mp
    assert "used_gb" in mp
    assert "available_gb" in mp
    assert "percent" in mp
    assert mp["total_gb"] > 0


def test_is_cpu_overloaded_returns_bool():
    assert isinstance(cpu_guard.is_cpu_overloaded(), bool)


def test_get_guard_state_initial():
    s = cpu_guard.get_guard_state()
    assert "samples_count" in s
    assert "consecutive_high" in s
    assert "triggered_gaming" in s
