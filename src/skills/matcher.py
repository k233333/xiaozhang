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
    """返回最佳匹配的 skill；没有则返回 None。

    三层匹配：
      1. 字面包含（覆盖率 >= 0.7）
      2. difflib 模糊相似度（>= threshold）
      3. ChromaDB 向量召回（如果启用）
    """
    if not user_text or not skills:
        return None

    text = user_text.strip()
    threshold = settings.skills.match_threshold

    # 1. 字面包含（带覆盖率约束）
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

    # 3. 向量召回（ChromaDB）
    if settings.memory.enable_vector:
        try:
            from src.memory.vector import query as vec_query  # noqa: PLC0415

            results = vec_query(text, n=1)
            if results:
                top = results[0]
                distance = top.get("distance", 999)
                # ChromaDB L2 距离：越小越相似。< 0.35 才算有效召回，否则退回 LLM 规划
                if distance < 0.35:
                    skill_name = top.get("skill_name", "")
                    matched = next((s for s in skills if s.name == skill_name), None)
                    if matched:
                        log.info(
                            "skill 向量命中",
                            skill=matched.name,
                            distance=round(distance, 3),
                        )
                        return matched
                else:
                    log.info(
                        "向量匹配距离过大，退回 LLM 规划",
                        skill=top.get("skill_name", "?"),
                        distance=round(distance, 3),
                    )
        except Exception as e:  # noqa: BLE001
            log.debug("向量召回失败（可忽略）", err=str(e))

    if best:
        log.info(
            "skill 最佳模糊匹配未达阈值，退回 LLM 规划",
            skill=best[0].name,
            trigger=best[1],
            ratio=round(best[2], 3),
            threshold=threshold,
        )
    return None
