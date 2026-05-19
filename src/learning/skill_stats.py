"""skill 调用统计

每次执行后调用 record()，结果累积进 knowledge-runtime.json → skill_stats。
后续 evolution.py 用这些数据决定是否重写 trigger / 删除低质量 skill。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

_lock = Lock()


def _path() -> Path:
    p = settings.resolve_path(settings.paths.knowledge_runtime)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("knowledge-runtime.json 损坏，重置")
        return {}


def _save(data: dict) -> None:
    _path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record(
    skill_name: str | None,
    *,
    success: bool,
    user_text: str = "",
    failure_reason: str = "",
) -> None:
    """记录一次 skill 调用结果。skill_name=None 表示是现规划（未命中 skill）。"""
    with _lock:
        data = _load()
        stats = data.setdefault("skill_stats", {})

        key = skill_name or "__live_planning__"
        entry = stats.setdefault(
            key,
            {
                "total": 0,
                "success": 0,
                "fail": 0,
                "last_success_ts": None,
                "last_failure_ts": None,
                "last_failure_reason": "",
                "recent_user_texts": [],
            },
        )
        entry["total"] += 1
        if success:
            entry["success"] += 1
            entry["last_success_ts"] = time.time()
        else:
            entry["fail"] += 1
            entry["last_failure_ts"] = time.time()
            entry["last_failure_reason"] = failure_reason

        if user_text:
            recents: list = entry.setdefault("recent_user_texts", [])
            recents.append({"text": user_text, "success": success, "ts": time.time()})
            # 只保留最近 20 条
            if len(recents) > 20:
                entry["recent_user_texts"] = recents[-20:]

        _save(data)
        log.info(
            "skill 统计",
            skill=key,
            success=entry["success"],
            total=entry["total"],
            success_rate=round(entry["success"] / entry["total"], 3),
        )


def get_stats(skill_name: str) -> dict:
    data = _load()
    return data.get("skill_stats", {}).get(skill_name, {})


def all_stats() -> dict:
    data = _load()
    return data.get("skill_stats", {})


def low_success_skills(min_calls: int = 5, threshold: float = 0.5) -> list[str]:
    """返回成功率低于阈值的 skill 名（用于 evolution）"""
    out: list[str] = []
    for name, s in all_stats().items():
        if name.startswith("__"):
            continue
        if s.get("total", 0) < min_calls:
            continue
        rate = s.get("success", 0) / max(1, s.get("total", 1))
        if rate < threshold:
            out.append(name)
    return out
