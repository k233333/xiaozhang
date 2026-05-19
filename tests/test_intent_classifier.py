"""意图复杂度分类器测试"""
from __future__ import annotations

from src.brain.intent_classifier import Complexity, classify


def test_empty_is_simple():
    assert classify("") == Complexity.SIMPLE
    assert classify("   ") == Complexity.SIMPLE


def test_short_is_simple():
    assert classify("打开抖音") == Complexity.SIMPLE
    assert classify("锁屏") == Complexity.SIMPLE
    assert classify("截图") == Complexity.SIMPLE
    assert classify("暂停") == Complexity.SIMPLE


def test_open_prefix_short_is_simple():
    assert classify("打开计算器") == Complexity.SIMPLE
    assert classify("启动Chrome") == Complexity.SIMPLE
    assert classify("关闭记事本") == Complexity.SIMPLE


def test_complex_keywords_trigger():
    assert classify("帮我把文件整理到桌面") == Complexity.COMPLEX
    assert classify("先打开浏览器然后搜索天气") == Complexity.COMPLEX
    assert classify("把所有截图按日期分类") == Complexity.COMPLEX
    assert classify("批量重命名 D 盘的照片") == Complexity.COMPLEX


def test_long_text_is_complex():
    assert classify("帮我把今天 D 盘所有大于 100MB 的临时文件按文件类型分类后压缩到桌面") == Complexity.COMPLEX


def test_medium_without_keywords_is_simple():
    """中等长度但没复杂关键词 → 简单"""
    assert classify("打开抖音搜不惑兄弟") == Complexity.SIMPLE  # 9 字
    assert classify("打开微信给妈妈发消息") == Complexity.SIMPLE  # 10 字


def test_borderline_cases():
    # 15 字以内 + 简单前缀 → 简单
    assert classify("打开 VS Code 项目") == Complexity.SIMPLE
    # 超过 25 字无关键词 → 复杂
    assert classify("我想看一下最近一周 GitHub 上 star 最多的 Python 项目") == Complexity.COMPLEX


def test_conditional_is_complex():
    assert classify("如果今天是周末就打开游戏") == Complexity.COMPLEX
