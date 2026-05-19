"""Action JSON 的 pydantic schema

Claude 输出的规划 JSON 必须能被这里的 Plan 接收。任何字段缺失/类型错误都拒绝执行。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Tier = Literal["D", "C", "A"]


class Step(BaseModel):
    """一步操作"""

    tier: Tier = Field(description="期望执行级别。D=URI/快捷键, C=控件树, A=Vision")
    action: str = Field(description="动作名，如 open_url / click / type / launch_app")
    description: str = Field(default="", description="人类可读说明，可空")

    # 各 action 的参数
    url: str | None = None
    text: str | None = None
    target: dict[str, Any] | None = Field(
        default=None,
        description="UIA 选择器，如 {automation_id, name, control_type}",
    )
    keys: str | None = Field(default=None, description="快捷键字符串，如 'ctrl+l'")
    cmd: list[str] | None = Field(default=None, description="subprocess argv")

    # 失败处理
    fallback_tier: Tier | None = None
    timeout_seconds: float = 10.0

    # 安全
    requires_confirmation: bool = False


class Plan(BaseModel):
    """完整规划：从用户意图到操作序列"""

    intent: str = Field(description="意图标识，如 watch_buhuxiongdi。snake_case")
    skill_hit: bool = Field(default=False, description="是否命中已有 skill")
    skill_name: str | None = None
    confirm_required: bool = False
    needs_complex_reasoning: bool = Field(
        default=False,
        description="LLM 自我标记：需要更强模型 escalate 到 v4-pro 重新规划",
    )
    steps: list[Step] = Field(default_factory=list)
    note: str = Field(default="", description="给用户的简短反馈，可空")

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls.model_validate(data)


class AmbiguousIntent(BaseModel):
    """意图模糊时的反问"""

    intent: Literal["ambiguous"] = "ambiguous"
    ask_user: str
