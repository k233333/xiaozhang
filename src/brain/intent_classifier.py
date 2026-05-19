"""轻量意图复杂度分类器（纯本地规则，0ms，不调 LLM）

在 skill 未命中后、调 LLM 之前运行。
根据用户原话的长度 + 关键词判断复杂度，决定走哪个路由：
  - simple  → task_planning（deepseek.v4，0.8s）
  - complex → task_planning_complex（deepseek.v4-pro，28s 但质量高）

设计原则：
  - 宁可把复杂任务误判为简单（v4 规划后 LLM 自标 needs_complex_reasoning 会 escalate）
  - 不能把简单任务误判为复杂（浪费 28s）
  - 所以阈值偏高：只有非常明确的复杂信号才直接走 v4-pro
"""
from __future__ import annotations

import re
from enum import Enum

from src.core.logger import get_logger

log = get_logger(__name__)


class Complexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


# 复杂任务关键词（含任一即判复杂）
_COMPLEX_KEYWORDS = [
    "然后", "之后", "接着", "并且", "同时", "先.*再", "再.*然后",
    "整理", "分类", "压缩", "批量", "所有", "每个", "遍历",
    "如果.*就", "判断", "条件",
    "按.*排序", "按.*分", "按日期", "按类型", "按大小",
]

_COMPLEX_PATTERNS = [re.compile(p) for p in _COMPLEX_KEYWORDS]

# 简单任务模式（命中即判简单，优先级高于复杂关键词）
_SIMPLE_PREFIXES = [
    "打开", "启动", "关闭", "退出", "切换到",
    "锁屏", "截图", "静音", "暂停", "播放",
    "音量", "上一首", "下一首", "显示桌面",
]


def classify(user_text: str) -> Complexity:
    """判断用户输入的复杂度。纯规则，0ms。"""
    text = user_text.strip()

    if not text:
        return Complexity.SIMPLE

    # 1. 极短文本（≤ 8 字）几乎一定是简单指令
    if len(text) <= 8:
        return Complexity.SIMPLE

    # 2. 以简单前缀开头 + 总长 ≤ 15 字 → 简单
    for prefix in _SIMPLE_PREFIXES:
        if text.startswith(prefix) and len(text) <= 15:
            return Complexity.SIMPLE

    # 3. 复杂关键词命中 → 复杂
    for pattern in _COMPLEX_PATTERNS:
        if pattern.search(text):
            log.debug("意图分类：复杂", text=text[:30], pattern=pattern.pattern)
            return Complexity.COMPLEX

    # 4. 长文本（> 25 字）且不是简单前缀 → 复杂
    if len(text) > 25:
        return Complexity.COMPLEX

    # 5. 默认简单
    return Complexity.SIMPLE
