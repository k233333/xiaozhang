"""Skill 加载 + 匹配测试"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.skills import loader, matcher


@pytest.fixture
def loaded_skills():
    """加载真实 builtin skills"""
    return loader.load_all()


def test_load_all_returns_list(loaded_skills):
    assert isinstance(loaded_skills, list)
    assert len(loaded_skills) > 0


def test_each_skill_has_required_fields(loaded_skills):
    for s in loaded_skills:
        assert s.name
        assert isinstance(s.path, Path)
        assert isinstance(s.triggers, list)
        # 至少有一个触发词
        assert len(s.triggers) >= 1


def test_builtin_open_douyin_loaded(loaded_skills):
    names = [s.name for s in loaded_skills]
    assert "open-douyin" in names


def test_match_literal_full_coverage(loaded_skills):
    """字面包含 + 覆盖率 >= 0.7 → 命中"""
    hit = matcher.match("打开抖音", loaded_skills)
    assert hit is not None
    assert hit.name == "open-douyin"


def test_match_long_intent_not_hijacked(loaded_skills):
    """短 trigger 不应该截胡长意图"""
    hit = matcher.match("打开抖音搜不惑兄弟", loaded_skills)
    # 当前 builtin 里 open-douyin trigger="打开抖音" 占输入比例 4/9 < 0.7
    # 应该走不到字面命中（除非有更长的 trigger 完全覆盖）
    if hit is not None:
        # 如果命中了，必须是覆盖率高的（比如更长的 trigger）
        assert any(t in "打开抖音搜不惑兄弟" and len(t) / 9 >= 0.7 for t in hit.triggers)


def test_match_no_match_returns_none(loaded_skills):
    hit = matcher.match("彻底不存在的奇怪话语 abc xyz", loaded_skills)
    assert hit is None


def test_match_empty_input(loaded_skills):
    assert matcher.match("", loaded_skills) is None
    assert matcher.match("   ", loaded_skills) is None


def test_match_empty_skills():
    assert matcher.match("打开抖音", []) is None


def test_lock_skill_match():
    skills = loader.load_all()
    hit = matcher.match("锁屏", skills)
    assert hit is not None
    assert hit.name == "system-lock"


def test_play_pause_skill_match():
    skills = loader.load_all()
    for word in ["暂停", "播放", "暂停音乐"]:
        hit = matcher.match(word, skills)
        assert hit is not None, f"{word} 应该命中 system-play-pause"
        assert hit.name == "system-play-pause"
