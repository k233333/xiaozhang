# coding: utf-8
"""JSON Skill — 视觉学习产出的轻量级 deterministic skill。

防爆约束：
- 同 selector + 同 domain 已存在 → 合并 trigger 而非新建
- 同名不同 selector → 加 -2 后缀
- 单 skill trigger ≤ 12
- prune() 主动清理低质量 / 久未使用 / 总数超限
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

MAX_TRIGGERS_PER_SKILL = 12


def _store_dir() -> Path:
    p = settings.resolve_path(settings.paths.skills_dir) / "_json"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class JsonSkill:
    name: str
    triggers: list[str] = field(default_factory=list)
    method: str = "playwright"
    selector: str = ""
    text_match: str | None = None
    target: dict[str, Any] | None = None
    fallback_method: str = ""
    fallback_x: int = 0
    fallback_y: int = 0
    page_url_hint: str = ""
    matched_text: str = ""
    learned_at: str = ""
    use_count: int = 0
    fail_count: int = 0
    last_failure: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "JsonSkill":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text.strip())
    return s.strip("_")[:60] or "unnamed"


def _domain_of(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse  # noqa: PLC0415
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def save(skill: JsonSkill) -> Path:
    if not skill.learned_at:
        skill.learned_at = datetime.now().isoformat(timespec="seconds")
    name = _slug(skill.name)
    path = _store_dir() / f"{name}.json"
    path.write_text(json.dumps(skill.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("JSON skill 已保存", name=skill.name, path=str(path))
    return path


def load_all() -> list[JsonSkill]:
    out: list[JsonSkill] = []
    for f in _store_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append(JsonSkill.from_dict(data))
        except Exception as e:
            log.warning("JSON skill 解析失败", path=str(f), err=str(e))
    return out


def find_by_name(name: str) -> JsonSkill | None:
    for s in load_all():
        if s.name == name:
            return s
    return None


def find_by_selector_and_domain(selector: str, page_url: str) -> JsonSkill | None:
    if not selector:
        return None
    domain = _domain_of(page_url)
    for s in load_all():
        if s.selector == selector and _domain_of(s.page_url_hint) == domain:
            return s
    return None


def update_stats(name: str, *, success: bool, failure_msg: str = "") -> None:
    skill = find_by_name(name)
    if skill is None:
        return
    skill.use_count += 1
    if not success:
        skill.fail_count += 1
        skill.last_failure = failure_msg[:200]
    save(skill)


def merge_triggers_into(skill: JsonSkill, new_triggers: list[str]) -> bool:
    existing = set(skill.triggers)
    added = False
    for t in new_triggers:
        t = t.strip()
        if not t or t in existing:
            continue
        if len(skill.triggers) >= MAX_TRIGGERS_PER_SKILL:
            break
        skill.triggers.append(t)
        existing.add(t)
        added = True
    if added:
        save(skill)
    return added


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match(user_text: str, skills: list[JsonSkill] | None = None) -> JsonSkill | None:
    if not user_text:
        return None
    text = user_text.strip()
    if skills is None:
        skills = load_all()
    if not skills:
        return None

    best_lit: tuple[JsonSkill, str, float] | None = None
    for s in skills:
        for trig in s.triggers:
            if trig and trig in text:
                cov = len(trig) / max(1, len(text))
                if cov >= 0.5:
                    if best_lit is None or cov > best_lit[2]:
                        best_lit = (s, trig, cov)
    if best_lit:
        log.info("JSON skill 字面命中", skill=best_lit[0].name,
                 trigger=best_lit[1], coverage=round(best_lit[2], 2))
        return best_lit[0]

    best: tuple[JsonSkill, str, float] | None = None
    for s in skills:
        for trig in s.triggers:
            if not trig:
                continue
            r = _ratio(text, trig)
            if best is None or r > best[2]:
                best = (s, trig, r)
    if best and best[2] >= 0.85:
        log.info("JSON skill 模糊命中", skill=best[0].name,
                 trigger=best[1], ratio=round(best[2], 3))
        return best[0]
    return None


def execute(skill: JsonSkill) -> tuple[bool, str]:
    method = skill.method.lower().strip()
    log.info("执行 JSON skill", name=skill.name, method=method)

    if method == "playwright":
        ok, msg = _exec_playwright(skill)
        if ok:
            update_stats(skill.name, success=True)
            return True, msg
        if skill.fallback_method == "click_xy":
            ok2, _ = _exec_click_xy(skill.fallback_x, skill.fallback_y)
            if ok2:
                update_stats(skill.name, success=True)
                return True, f"playwright 失败({msg})，坐标兜底成功"
        update_stats(skill.name, success=False, failure_msg=msg)
        return False, msg

    if method == "uia":
        ok, msg = _exec_uia(skill)
        if ok:
            update_stats(skill.name, success=True)
            return True, msg
        if skill.fallback_method == "click_xy":
            ok2, _ = _exec_click_xy(skill.fallback_x, skill.fallback_y)
            if ok2:
                update_stats(skill.name, success=True)
                return True, f"uia 失败({msg})，坐标兜底成功"
        update_stats(skill.name, success=False, failure_msg=msg)
        return False, msg

    if method == "click_xy":
        ok, msg = _exec_click_xy(skill.fallback_x, skill.fallback_y)
        update_stats(skill.name, success=ok, failure_msg=msg if not ok else "")
        return ok, msg

    update_stats(skill.name, success=False, failure_msg=f"未知 method: {method}")
    return False, f"未知 method: {method}"


def _exec_playwright(skill: JsonSkill) -> tuple[bool, str]:
    from src.actions.playwright_action import playwright_click  # noqa: PLC0415
    if not skill.selector:
        return False, "playwright skill 没有 selector"
    res = playwright_click(skill.selector, text_match=skill.text_match)
    return res.success, res.message


def _exec_click_xy(x: int, y: int) -> tuple[bool, str]:
    from src.actions.raw_input import click_xy  # noqa: PLC0415
    if x <= 0 or y <= 0:
        return False, f"无效坐标 ({x},{y})"
    ok = click_xy(x, y)
    return ok, "" if ok else "click_xy 失败"


def _exec_uia(skill: JsonSkill) -> tuple[bool, str]:
    import asyncio  # noqa: PLC0415
    from src.actions import tier_c_uia  # noqa: PLC0415
    from src.brain.action_schema import Step  # noqa: PLC0415
    if not skill.target:
        return False, "uia skill 没有 target"
    step = Step(tier="C", action="click", target=skill.target)
    try:
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(tier_c_uia.execute(step))
        finally:
            loop.close()
        return res.success, res.message
    except Exception as e:
        return False, f"uia 异常: {e}"


def learn_chrome_click(*, triggers: list[str], description: str,
                       skill_name: str | None = None) -> JsonSkill | None:
    from src.actions.playwright_action import find_element_by_description  # noqa: PLC0415

    found = find_element_by_description(description)
    if found is None:
        return None
    selector = found["selector"]
    page_url = found.get("page_url", "")

    existing = find_by_selector_and_domain(selector, page_url)
    if existing is not None:
        merge_triggers_into(existing, triggers + [description])
        return existing

    name = skill_name or _slug(description)
    if find_by_name(name) is not None:
        suffix = 2
        while find_by_name(f"{name}-{suffix}") is not None:
            suffix += 1
        name = f"{name}-{suffix}"

    skill = JsonSkill(
        name=name,
        triggers=triggers[:MAX_TRIGGERS_PER_SKILL],
        method="playwright",
        selector=selector,
        text_match=None,
        matched_text=found.get("matched_text", ""),
        page_url_hint=page_url,
    )
    bbox = found.get("bbox")
    if bbox:
        skill.fallback_method = "click_xy"
        skill.fallback_x = bbox[0] + bbox[2] // 2
        skill.fallback_y = bbox[1] + bbox[3] // 2
    save(skill)
    return skill


def learn_screen_click(*, triggers: list[str], description: str, x: int, y: int,
                       matched_text: str = "", skill_name: str | None = None) -> JsonSkill | None:
    """从 OCR 学习一个坐标 skill（method=click_xy）。"""
    name = skill_name or _slug(description)
    if find_by_name(name) is not None:
        suffix = 2
        while find_by_name(f"{name}-{suffix}") is not None:
            suffix += 1
        name = f"{name}-{suffix}"

    skill = JsonSkill(
        name=name,
        triggers=triggers[:MAX_TRIGGERS_PER_SKILL],
        method="click_xy",
        fallback_method="click_xy",
        fallback_x=x,
        fallback_y=y,
        matched_text=matched_text or description,
    )
    save(skill)
    return skill


def prune(*, max_skills: int = 200,
          delete_zero_use_older_than_days: int = 30,
          delete_high_fail_threshold: float = 0.7,
          min_calls_for_quality_check: int = 5,
          dry_run: bool = False) -> dict:
    skills = load_all()
    deletions: list[tuple[JsonSkill, str]] = []
    for s in skills:
        if s.use_count == 0:
            try:
                ts = datetime.fromisoformat(s.learned_at).timestamp() if s.learned_at else 0
            except Exception:
                ts = 0
            age_days = (time.time() - ts) / 86400 if ts else 999
            if age_days > delete_zero_use_older_than_days:
                deletions.append((s, f"未使用且 {int(age_days)} 天前学的"))
    for s in skills:
        if s.use_count >= min_calls_for_quality_check:
            fail_rate = s.fail_count / s.use_count
            if fail_rate >= delete_high_fail_threshold:
                deletions.append((s, f"失败率 {fail_rate:.0%}"))

    surviving_names = {s.name for s in skills} - {d[0].name for d in deletions}
    if len(surviving_names) > max_skills:
        target = int(max_skills * 0.8)
        surviving = [s for s in skills if s.name in surviving_names]
        ranked = sorted(surviving, key=lambda x: (x.use_count, x.learned_at or ""))
        excess = len(surviving) - target
        for s in ranked[:excess]:
            deletions.append((s, "总数超限，LRU 淘汰"))

    seen: set[str] = set()
    unique_deletions: list[tuple[JsonSkill, str]] = []
    for s, reason in deletions:
        if s.name in seen:
            continue
        seen.add(s.name)
        unique_deletions.append((s, reason))

    if not dry_run:
        for s, _ in unique_deletions:
            path = _store_dir() / f"{_slug(s.name)}.json"
            if path.exists():
                path.unlink()
                log.info("删除 JSON skill", name=s.name, path=str(path))

    return {
        "kept": len(skills) - len(unique_deletions),
        "deleted": [(s.name, r) for s, r in unique_deletions],
        "total_before": len(skills),
    }
