"""加载 skills/ 下所有 SKILL.md → SkillSpec 列表

解析逻辑已抽到 src/skills/parser.py（v2.0）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.brain.action_schema import Step
from src.core.config import settings
from src.core.logger import get_logger
from src.skills.parser import parse

log = get_logger(__name__)


@dataclass
class SkillSpec:
    name: str
    path: Path
    description: str
    triggers: list[str] = field(default_factory=list)
    confirm_required: bool = False
    steps: list[Step] = field(default_factory=list)
    learned: list[str] = field(default_factory=list)
    frontmatter: dict = field(default_factory=dict)


def load_skill_dir(dir_path: Path) -> SkillSpec | None:
    md_path = dir_path / "SKILL.md"
    if not md_path.exists():
        return None
    text = md_path.read_text(encoding="utf-8")
    parsed = parse(text)

    steps: list[Step] = []
    for raw in parsed.steps_raw:
        try:
            steps.append(Step.model_validate(raw))
        except Exception as e:  # noqa: BLE001
            log.warning("skill 中的某步无法解析", skill=dir_path.name, err=str(e))

    return SkillSpec(
        name=dir_path.name,
        path=dir_path,
        description=parsed.description or parsed.frontmatter.get("description", ""),
        triggers=parsed.triggers,
        confirm_required=parsed.confirm_required,
        steps=steps,
        learned=parsed.learned,
        frontmatter=parsed.frontmatter,
    )


def load_all() -> list[SkillSpec]:
    out: list[SkillSpec] = []
    for base in (settings.skills.builtin_dir, settings.skills.generated_dir):
        root = settings.resolve_path(base)
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            spec = load_skill_dir(child)
            if spec is not None:
                out.append(spec)
    log.info("skills 加载完成", count=len(out))
    return out
