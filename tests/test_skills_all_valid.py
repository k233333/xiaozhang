"""校验所有 builtin SKILL.md 都是合法可执行的（防止有人手写错）"""
from __future__ import annotations

from src.skills import loader


def test_all_builtin_skills_load():
    skills = loader.load_all()
    builtin = [s for s in skills if "_builtin" in str(s.path)]
    assert len(builtin) >= 20  # D 阶段我们至少有 20+ builtin


def test_all_skills_have_at_least_one_step():
    for s in loader.load_all():
        assert len(s.steps) >= 1, f"{s.name} 没有任何 step"


def test_all_skills_have_at_least_one_trigger():
    for s in loader.load_all():
        assert len(s.triggers) >= 1, f"{s.name} 没有任何 trigger"


def test_all_skill_steps_have_valid_tier():
    for s in loader.load_all():
        for step in s.steps:
            assert step.tier in ("D", "C", "A"), (
                f"{s.name} 中存在非法 tier={step.tier}"
            )


def test_no_duplicate_skill_names():
    names = [s.name for s in loader.load_all()]
    assert len(names) == len(set(names)), "skill 名重复"


def test_open_url_steps_have_url():
    for s in loader.load_all():
        for step in s.steps:
            if step.action == "open_url":
                assert step.url, f"{s.name} 的 open_url step 缺 url"


def test_launch_app_steps_have_cmd_or_url():
    for s in loader.load_all():
        for step in s.steps:
            if step.action == "launch_app":
                assert step.cmd or step.url, (
                    f"{s.name} 的 launch_app step 缺 cmd/url"
                )


def test_keys_steps_have_keys():
    for s in loader.load_all():
        for step in s.steps:
            if step.action == "keys":
                assert step.keys, f"{s.name} 的 keys step 缺 keys 字段"
