"""把成功执行的 plan 自动沉淀为 skill

仿 Friday 的 BrowserRecorder + WorkflowExecutor 思路。
触发时机：plan 执行成功 + 不是 skill_hit（即本次走的是现规划）。

成功条件：
  - 所有 step 都成功
  - 整体 < 30 秒（防止超长流程难复用）
  - intent 不是 ambiguous
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src.actions.executor import PlanReport
from src.core.config import settings
from src.core.logger import get_logger
from src.skills.generator import generate_skill

log = get_logger(__name__)

MAX_RECORD_SECONDS = 30.0


async def maybe_record(report: PlanReport, *, user_text: str) -> Path | None:
    """如果满足沉淀条件，自动产出 skill"""
    plan = report.plan
    if not report.all_succeeded():
        return None
    if plan.skill_hit:
        return None  # 命中已有 skill，无需再录
    if plan.intent in ("", "ambiguous", "unknown"):
        return None
    total_elapsed = sum(s.elapsed_sec for s in report.steps)
    if total_elapsed > MAX_RECORD_SECONDS:
        log.info("plan 超长，不沉淀为 skill", elapsed=total_elapsed)
        return None

    log.info("成功执行，沉淀新 skill", intent=plan.intent, user_text=user_text)
    path = await generate_skill(user_text=user_text, plan=plan, outcome="自动录制")
    if path is not None:
        _index_skill(plan.intent, str(path), user_text)
    return path


def _index_skill(intent: str, path: str, user_text: str) -> None:
    """在 knowledge-runtime.json → always_skill_match 追加索引"""
    p = settings.resolve_path(settings.paths.knowledge_runtime)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("knowledge-runtime.json 损坏，跳过索引")
        return
    matches: list = data.setdefault("always_skill_match", [])
    # 去重
    if any(m.get("intent") == intent for m in matches):
        return
    matches.append(
        {
            "intent": intent,
            "skill_path": path,
            "trigger_seed": user_text,
            "created_at": time.time(),
        }
    )
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("skill 索引已更新", intent=intent)
