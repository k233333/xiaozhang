"""LLMRouter 测试（不发真实 API 请求）"""
from __future__ import annotations

import pytest

from src.brain.llm_router import LLMRouter, extract_json


def test_extract_json_from_code_block():
    text = '```json\n{"intent": "test"}\n```'
    assert extract_json(text) == {"intent": "test"}


def test_extract_json_from_naked():
    text = '{"intent": "test", "x": 1}'
    assert extract_json(text) == {"intent": "test", "x": 1}


def test_extract_json_with_text_around():
    text = "好的，这是规划：\n```json\n{\"intent\": \"x\"}\n```\n感谢"
    assert extract_json(text) == {"intent": "x"}


def test_extract_json_invalid():
    assert extract_json("not json at all") is None


def test_extract_json_truncated():
    """带前后噪声的裸 JSON"""
    text = "Some preamble {\"intent\": \"x\", \"v\": 1} trailing"
    r = extract_json(text)
    assert r == {"intent": "x", "v": 1}


@pytest.mark.asyncio
async def test_router_complete_unknown_task_returns_none():
    r = LLMRouter()
    result = await r.complete("nonexistent_task", system="x", user="y")
    assert result is None


@pytest.mark.asyncio
async def test_router_complete_json_returns_none_on_failure():
    """没配 task 路由时 complete_json 也优雅返回 None"""
    r = LLMRouter()
    result = await r.complete_json("nonexistent_task", system="x", user="y")
    assert result is None
