"""Skill 触发词匹配

阶段 1（D6-7 当前）：纯字面包含 + difflib 模糊相似度。
阶段 2（后续）：接 ChromaDB 向量召回（vector.py）。
"""
from __future__ import annotations

from difflib import SequenceMatcher

from src.core.config import settings
from src.core.logger import get_logger
from src.skills.loader import SkillSpec

log = get_logger(__name__)


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match(user_text: str, skills: list[SkillSpec]) -> SkillSpec | None:
    """返回最佳匹配（高于阈值）的 skill；没有则返回 None。"""
    if not user_text or not skills:
        return None

    text = user_text.strip()
    threshold = settings.skills.match_threshold

    # 1. 字面包含优先（但要求覆盖率达标，避免短 trigger 把长意图截胡）
    # 例如"打开抖音"包含在"打开抖音搜不惑兄弟"里，但后者的真实意图是搜索；
    # 只有 trigger 占用户文本长度比例 >= 0.7 才算字面命中。
    coverage_threshold = 0.7
    best_literal: tuple[SkillSpec, str, float] | None = None
    for s in skills:
        for trig in s.triggers:
            if trig and trig in text:
                coverage = len(trig) / max(1, len(text))
                if coverage >= coverage_threshold:
                    if best_literal is None or coverage > best_literal[2]:
                        best_literal = (s, trig, coverage)
    if best_literal:
        log.info(
            "skill 字面命中",
            skill=best_literal[0].name,
            trigger=best_literal[1],
            coverage=round(best_literal[2], 2),
        )
        return best_literal[0]

    # 2. 模糊相似
    best: tuple[SkillSpec, str, float] | None = None
    for s in skills:
        for trig in s.triggers:
            if not trig:
                continue
            r = _ratio(text, trig)
            if best is None or r > best[2]:
                best = (s, trig, r)
    if best and best[2] >= threshold:
        log.info(
            "skill 模糊命中",
            skill=best[0].name,
            trigger=best[1],
            ratio=round(best[2], 3),
        )
        return best[0]
    if best:
        log.debug(
            "skill 最佳模糊匹配未达阈值",
            skill=best[0].name,
            trigger=best[1],
            ratio=round(best[2], 3),
            threshold=threshold,
        )
    return None
