"""skill 自我进化（受 Hermes/GEPA 启发，简化实现）

定期调用：
  1. 找出成功率 < 50% 且调用 ≥ 5 次的 skill
  2. 把它的 trigger + 最近失败的 user_text 喂给 LLM，让它重写 triggers
  3. 备份原 SKILL.md，写入新版

不删 skill（除非用户明确要求），只改 trigger。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from src.brain.llm_router import chat_simple
from src.core.config import settings
from src.core.logger import get_logger
from src.learning import skill_stats
from src.skills.loader import load_all

log = get_logger(__name__)


_REWRITE_SYSTEM = """你是 skill trigger 优化助手。
用户给你一个 skill 的当前 trigger 列表 + 最近失败的用户原话。
请重写 triggers（3-6 个），让模糊匹配更容易命中。
只输出新 triggers，每行一个，不输出任何解释。
"""


async def evolve_low_quality_skills() -> list[str]:
    """重写所有低质量 skill 的 trigger。返回被重写的 skill 名列表。"""
    targets = skill_stats.low_success_skills()
    if not targets:
        return []

    skills = {s.name: s for s in load_all()}
    changed: list[str] = []

    for name in targets:
        spec = skills.get(name)
        if spec is None:
            continue

        stats = skill_stats.get_stats(name)
        recent_fails = [
            r["text"] for r in stats.get("recent_user_texts", []) if not r.get("success")
        ][-10:]

        prompt = (
            f"当前 triggers：\n"
            + "\n".join(f"- {t}" for t in spec.triggers)
            + "\n\n最近失败的用户原话：\n"
            + "\n".join(f"- {t}" for t in recent_fails)
        )
        try:
            new_text = await chat_simple(prompt, system=_REWRITE_SYSTEM)
        except Exception as e:  # noqa: BLE001
            log.warning("evolve 调用 LLM 失败", err=str(e))
            continue

        new_triggers = [
            line.lstrip("-* ").strip()
            for line in new_text.splitlines()
            if line.strip()
        ][:6]
        if not new_triggers:
            continue

        log.info("skill 进化", skill=name, old=spec.triggers, new=new_triggers)
        _rewrite_skill_triggers(spec.path, new_triggers)
        changed.append(name)

    return changed


def _rewrite_skill_triggers(skill_dir: Path, new_triggers: list[str]) -> None:
    md_path = skill_dir / "SKILL.md"
    if not md_path.exists():
        return
    backup = skill_dir / "SKILL.md.bak"
    shutil.copyfile(md_path, backup)

    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    out: list[str] = []
    in_triggers = False
    replaced = False
    for line in lines:
        if line.strip().lower().startswith("## triggers"):
            out.append(line)
            in_triggers = True
            for t in new_triggers:
                out.append(f"- {t}")
            replaced = True
            continue
        if in_triggers:
            if line.strip().startswith("-"):
                continue  # 跳过原 triggers
            if line.strip().startswith("##"):
                in_triggers = False
                out.append(line)
                continue
            if not line.strip():
                continue
            in_triggers = False
            out.append(line)
        else:
            out.append(line)

    if not replaced:
        # 没找到现有的 triggers section，追加一个
        out.append("\n## triggers")
        for t in new_triggers:
            out.append(f"- {t}")

    md_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    log.info("triggers 重写", path=str(md_path))
