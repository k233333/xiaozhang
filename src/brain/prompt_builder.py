"""动态 System Prompt 构建器 — Token 优化核心

设计原则：
  1. 静态内容放最前面（soul + core rules）→ 命中 DeepSeek 前缀缓存（1/10 价格）
  2. 动态内容放最后面（时间、上下文）→ 不破坏缓存前缀
  3. 按任务复杂度选择 prompt 级别：
     - simple: core only (~800 tokens)
     - complex: core + examples (~1500 tokens)
     - full: core + examples + platform details (旧 planner.md, ~2500 tokens)

优化效果：
  - 简单任务（"打开计算器"）：system prompt 从 ~3000 tokens → ~1200 tokens（省 60%）
  - 复杂任务保持完整 prompt 不降质量
  - 前缀缓存命中率从 ~0% → ~80%（soul + core 部分每次都一样）
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.logger import get_logger

log = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


# ---------- 静态内容缓存（进程生命周期内不变）----------

@lru_cache(maxsize=1)
def _soul() -> str:
    """人设（最高优先级，永远在最前面）"""
    p = _CONFIG_DIR / "soul.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _planner_core() -> str:
    """规划器核心规则（静态，可缓存）"""
    p = _PROMPTS_DIR / "planner_core.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _planner_examples() -> str:
    """规划器示例（仅复杂任务需要）"""
    p = _PROMPTS_DIR / "planner_examples.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _planner_full() -> str:
    """完整旧版 planner（最复杂任务兜底）"""
    p = _PROMPTS_DIR / "planner.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _skill_creator() -> str:
    p = _PROMPTS_DIR / "skill_creator.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


# ---------- Caveman 输出约束（减少输出 tokens）----------

_CAVEMAN_SUFFIX = """
## 输出风格约束
- note 字段：≤15 字，不用"好的"开头
- description：≤10 字
- 不输出多余空格/换行
- JSON 紧凑格式（无缩进）"""


# ---------- 构建器 ----------

def build_planning_prompt(
    *,
    complexity: str = "simple",
    extra_context: str = "",
) -> str:
    """构建规划用 system prompt。

    结构（从上到下）：
      [静态区 — 可被 DeepSeek 前缀缓存]
        1. soul.md（人设）
        2. planner_core.md（核心规则 + action 表）
        3. planner_examples.md（仅 complex/full）
      [动态区 — 不破坏缓存]
        4. Caveman 输出约束
        5. extra_context（如有）

    Args:
        complexity: "simple" | "complex" | "full"
        extra_context: 运行时上下文（失败记录、memory 召回等）
    """
    parts: list[str] = []

    # === 静态区（前缀缓存友好）===
    soul = _soul()
    if soul:
        parts.append(soul)

    parts.append(_planner_core())

    if complexity in ("complex", "full"):
        examples = _planner_examples()
        if examples:
            parts.append(examples)

    if complexity == "full":
        # 极复杂任务用完整旧版 prompt（含平台详细步骤）
        full = _planner_full()
        if full:
            parts.append(full)

    # === 动态区（放最后，不破坏前缀缓存）===
    parts.append(_CAVEMAN_SUFFIX)

    if extra_context:
        parts.append(f"\n## 运行时上下文\n{extra_context}")

    return "\n\n---\n\n".join(parts)


def build_skill_creator_prompt() -> str:
    """构建 skill 生成用 system prompt。"""
    parts = [_soul(), _skill_creator()]
    parts.append(_CAVEMAN_SUFFIX)
    return "\n\n---\n\n".join(p for p in parts if p)


def build_simple_chat_prompt(system_override: str = "") -> str:
    """构建简单对话用 system prompt（最精简）。"""
    soul = _soul()
    if system_override:
        return f"{soul}\n\n---\n\n{system_override}".strip() if soul else system_override
    return soul


def build_vision_prompt() -> str:
    """构建视觉分析用 system prompt（精简，不需要完整规划规则）。"""
    return _soul()
