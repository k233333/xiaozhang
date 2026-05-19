"""skill_stats 学习追踪测试"""
from __future__ import annotations

from src.learning import skill_stats


def test_record_first_success():
    skill_stats.record("test-skill", success=True, user_text="嗨")
    s = skill_stats.get_stats("test-skill")
    assert s["total"] == 1
    assert s["success"] == 1
    assert s["fail"] == 0


def test_record_failure():
    skill_stats.record("test-skill", success=True, user_text="x")
    skill_stats.record("test-skill", success=False, user_text="y", failure_reason="网络错误")
    s = skill_stats.get_stats("test-skill")
    assert s["total"] == 2
    assert s["success"] == 1
    assert s["fail"] == 1
    assert s["last_failure_reason"] == "网络错误"


def test_recent_user_texts_capped():
    """recent_user_texts 不超过 20 条"""
    for i in range(30):
        skill_stats.record("skill-x", success=True, user_text=f"输入 {i}")
    s = skill_stats.get_stats("skill-x")
    assert len(s["recent_user_texts"]) == 20
    # 应该是最新的 20 条
    last_text = s["recent_user_texts"][-1]["text"]
    assert "29" in last_text


def test_low_success_skills():
    """筛选低质量 skill"""
    # 一个高质量
    for _ in range(10):
        skill_stats.record("good", success=True)
    # 一个低质量
    for _ in range(10):
        skill_stats.record("bad", success=False)
    targets = skill_stats.low_success_skills(min_calls=5, threshold=0.5)
    assert "bad" in targets
    assert "good" not in targets


def test_low_success_ignores_low_call_count():
    skill_stats.record("rare-fail", success=False)
    skill_stats.record("rare-fail", success=False)
    targets = skill_stats.low_success_skills(min_calls=5, threshold=0.5)
    assert "rare-fail" not in targets  # 调用次数不够，不重写


def test_live_planning_excluded_from_low_success():
    """__live_planning__ 不应被 evolution 重写"""
    for _ in range(10):
        skill_stats.record(None, success=False)  # None → __live_planning__
    targets = skill_stats.low_success_skills(min_calls=5, threshold=0.5)
    assert "__live_planning__" not in targets
