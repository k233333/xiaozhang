"""跨会话回忆 + LLM 摘要

提供给规划阶段的"已知上下文"字符串：
  - 最近 N 条成功 session（intent + user_text + note）
  - 用户画像摘要

LLM 摘要更新（每 N 个会话触发一次）放在 update_user_profile()。
"""
from __future__ import annotations

from src.core.config import settings
from src.core.logger import get_logger
from src.memory import store, user_profile

log = get_logger(__name__)


def build_context(user_text: str, max_items: int = 5) -> str:
    """生成给 LLM 的"已知上下文"片段"""
    pieces: list[str] = []

    profile = user_profile.read()
    pieces.append("## 用户画像\n" + profile.strip())

    sessions = store.recent_sessions(limit=settings.memory.recent_session_lookback)
    if sessions:
        pieces.append("## 最近会话")
        for s in sessions[:max_items]:
            if not s.get("intent"):
                continue
            pieces.append(
                f"- [{s['intent']}] {s.get('user_text', '')} → "
                f"{'成功' if s.get('success') else '失败'} {s.get('note') or ''}"
            )

    return "\n".join(pieces)


async def update_user_profile_via_llm() -> None:
    """周期性把最近会话喂给 LLM 摘要更新画像。先留接口，D6-7 阶段再启用。"""
    from src.brain.llm_router import chat_simple  # noqa: PLC0415

    sessions = store.recent_sessions(limit=20)
    if not sessions:
        return
    summary_input = "\n".join(
        f"- [{s.get('intent')}] {s.get('user_text', '')} → {s.get('note', '')}"
        for s in sessions
    )
    profile = user_profile.read()
    new_profile = await chat_simple(
        f"基于以下会话历史，更新用户画像。保持 markdown 结构，只改内容不改格式。\n\n"
        f"## 当前画像\n{profile}\n\n## 最近会话\n{summary_input}",
        system="你是一个谨慎的画像维护助手，只补充确凿的信息，不臆测。",
    )
    if new_profile.strip():
        user_profile.write(new_profile)
