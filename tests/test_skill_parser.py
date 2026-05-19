"""SKILL.md parser 测试"""
from __future__ import annotations

from src.skills.parser import parse


def test_parse_complete_skill():
    text = """---
name: test
description: 测试
allowed-tools:
  - open_url
---

# test

## triggers
- 打开抖音
- 抖音

## description
打开抖音首页

## confirm_required
false

## steps
```json
[{"tier": "D", "action": "open_url", "url": "https://www.douyin.com"}]
```

## learned
- 抖音反爬较强
"""
    p = parse(text)
    assert p.frontmatter["name"] == "test"
    assert p.frontmatter["allowed-tools"] == ["open_url"]
    assert p.triggers == ["打开抖音", "抖音"]
    assert p.description == "打开抖音首页"
    assert p.confirm_required is False
    assert len(p.steps_raw) == 1
    assert p.steps_raw[0]["action"] == "open_url"
    assert p.learned == ["抖音反爬较强"]


def test_parse_no_frontmatter():
    text = """## triggers
- 测试

## steps
```json
[{"tier": "D", "action": "say", "text": "hi"}]
```
"""
    p = parse(text)
    assert p.frontmatter == {}
    assert p.triggers == ["测试"]
    assert len(p.steps_raw) == 1


def test_parse_confirm_required_true():
    text = """## confirm_required
true

## triggers
- x
"""
    p = parse(text)
    assert p.confirm_required is True


def test_parse_invalid_json_steps_safe():
    """JSON 损坏也不应该 raise"""
    text = """## triggers
- x

## steps
```json
{ broken json
```
"""
    p = parse(text)
    assert p.triggers == ["x"]
    assert p.steps_raw == []  # 容错


def test_parse_empty_text():
    p = parse("")
    assert p.triggers == []
    assert p.steps_raw == []
    assert p.description == ""
