"""任务成功后自动生成 SKILL.md

调用 brain.llm_router.chat_simple()，把执行链喂给 skill_creator prompt，
拿到 markdown 文本写入 skills/_generated/<intent>/SKILL.md。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.brain.action_schema import Plan
from src.brain.llm_router import chat_simple
from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "brain" / "prompts" / "skill_creator.md"


def _slug(text: str) -> str:
    """把 intent 转为合法目录名"""
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text.strip())
    return s.strip("_") or "unnamed_skill"


async def generate_skill(
    *,
    user_text: str,
    plan: Plan,
    outcome: str = "成功",
    overwrite: bool = False,
) -> Path | None:
    """根据成功执行的 plan 产出新 SKILL.md"""
    intent_slug = _slug(plan.intent)
    target_dir = settings.resolve_path(settings.skills.generated_dir) / intent_slug
    target_md = target_dir / "SKILL.md"

    if target_md.exists() and not overwrite:
        log.info("skill 已存在，跳过生成", path=str(target_md))
        return target_md

    target_dir.mkdir(parents=True, exist_ok=True)

    if not _PROMPT_PATH.exists():
        log.warning("skill_creator prompt 不存在，使用最小模板")
        md = _fallback_template(user_text, plan, outcome)
    else:
        from src.brain.prompt_builder import build_skill_creator_prompt  # noqa: PLC0415

        system = build_skill_creator_prompt()
        payload = {
            "user_text": user_text,
            "intent": plan.intent,
            "executed_steps": [s.model_dump(exclude_none=True) for s in plan.steps],
            "outcome": outcome,
        }
        try:
            md = await chat_simple(
                f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```",
                system=system,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("LLM 生成 skill 失败，使用最小模板", err=str(e))
            md = _fallback_template(user_text, plan, outcome)

    target_md.write_text(md.strip() + "\n", encoding="utf-8")
    log.info("skill 已生成", path=str(target_md), intent=plan.intent)
    return target_md


def _fallback_template(user_text: str, plan: Plan, outcome: str) -> str:
    """LLM 不可用时的最简模板"""
    triggers = [user_text.strip()]
    steps_json = json.dumps(
        [s.model_dump(exclude_none=True) for s in plan.steps],
        ensure_ascii=False,
        indent=2,
    )
    return f"""# {plan.intent}

## triggers
- {triggers[0]}

## description
{plan.note or '由系统兜底生成'}

## confirm_required
{str(plan.confirm_required).lower()}

## steps
```json
{steps_json}
```

## learned
- 自动生成于本次成功执行（{outcome}）
"""
