"""SKILL.md 解析器（v2.0 拆出来的）

支持：
  - 可选 frontmatter（YAML）
  - ## triggers   每行一个
  - ## description
  - ## confirm_required
  - ## steps      JSON code block
  - ## learned    每行一项
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml

from src.core.logger import get_logger

log = get_logger(__name__)


_FRONTMATTER_RE = re.compile(r"^---\s*\n([\s\S]*?)\n---\s*\n", re.MULTILINE)
_HEADING_RE = re.compile(r"^##\s+([\w\-]+)\s*$", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.MULTILINE)


@dataclass
class ParsedSkill:
    raw_text: str
    frontmatter: dict
    triggers: list[str]
    description: str
    confirm_required: bool
    steps_raw: list[dict]
    learned: list[str]


def parse(text: str) -> ParsedSkill:
    body = text
    fm: dict = {}
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError as e:
            log.warning("frontmatter 解析失败", err=str(e))
        body = text[fm_match.end():]

    sections = _split_sections(body)

    triggers = _list_items(sections.get("triggers", ""))
    description = sections.get("description", "").strip()
    confirm_required = sections.get("confirm_required", "").strip().lower() in (
        "true", "1", "yes",
    )

    steps_raw: list[dict] = []
    if "steps" in sections:
        m = _CODE_BLOCK_RE.search(sections["steps"])
        if m:
            try:
                steps_raw = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                log.warning("steps JSON 解析失败", err=str(e))

    learned = _list_items(sections.get("learned", ""))

    return ParsedSkill(
        raw_text=text,
        frontmatter=fm,
        triggers=triggers,
        description=description,
        confirm_required=confirm_required,
        steps_raw=steps_raw,
        learned=learned,
    )


def _split_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end]
    return sections


def _list_items(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith(("-", "*")):
            out.append(line.lstrip("-* ").strip())
    return out
