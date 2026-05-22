"""运行时主流程（v3.0 — Hermes 作为大脑）

小张进程只负责音频层（唤醒词+录音+ASR+TTS+气泡）+ 资源管理。
所有决策和执行由 Hermes 完成：
  - 本地 skill 匹配 → Hermes 的 skill 系统处理
  - LLM 规划 → Hermes 调 DeepSeek/Groq
  - 桌面操作 → Hermes 调 xz.py

调用方式：Hermes Python Library（进程内，零启动开销）
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from src.core.logger import get_logger, new_trace_id
from src.core.state_machine import State, StateMachine
from src.memory import store

log = get_logger(__name__)

# Hermes agent 单例（常驻内存，不重复初始化）
_agent = None


def _get_agent():
    """获取或创建 Hermes AIAgent 单例"""
    global _agent
    if _agent is not None:
        return _agent

    # 将 hermes-agent 加入 Python path
    hermes_path = r"D:\11111begin\hermes-agent"
    if hermes_path not in sys.path:
        sys.path.insert(0, hermes_path)

    try:
        from run_agent import AIAgent

        _agent = AIAgent(
            model="deepseek-chat",
            quiet_mode=True,
            enabled_toolsets=["terminal", "skills"],
            max_iterations=30,
        )
        log.info("Hermes AIAgent 初始化完成")
        return _agent
    except Exception as e:
        log.error("Hermes AIAgent 初始化失败", err=str(e))
        return None


@dataclass
class TurnResult:
    """一轮交互的结果"""
    user_text: str
    success: bool
    note: str = ""
    skill_hit: bool = False
    plan: object = None
    report: object = None


async def run_turn(user_text: str, sm: StateMachine | None = None) -> TurnResult:
    """处理一句用户输入 — 全部交给 Hermes。

    Hermes 内部会：
      1. 匹配 skill（如果有）→ 直接执行
      2. 没命中 → LLM 规划 → 调 xz.py 执行
    """
    import asyncio

    new_trace_id()

    user_text = (user_text or "").strip()
    if not user_text:
        return TurnResult(user_text=user_text, success=False, note="空输入")

    session_id = store.start_session(user_text=user_text)
    store.add_event(session_id, "transcript", user_text)

    if sm is not None:
        await sm.transition(State.EXECUTING)

    try:
        agent = _get_agent()
        if agent is None:
            store.end_session(session_id, success=False, note="Hermes 不可用")
            return TurnResult(
                user_text=user_text,
                success=False,
                note="Hermes 初始化失败，请检查 hermes-agent 安装",
            )

        # 在线程池中调用 Hermes（它是同步的）
        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, agent.chat, user_text)

        reply = (reply or "").strip()
        success = bool(reply)

        log.info("Hermes 回复", reply=reply[:100], success=success)
        store.add_event(session_id, "hermes_reply", reply[:500])
        store.end_session(session_id, success=success, note=reply[:200])

        return TurnResult(
            user_text=user_text,
            success=success,
            note=reply or "已完成",
        )

    except Exception as e:
        log.exception("Hermes 调用异常", err=str(e))
        store.end_session(session_id, success=False, note=str(e)[:200])
        return TurnResult(
            user_text=user_text,
            success=False,
            note=f"执行出错: {e}",
        )

    finally:
        if sm is not None:
            await sm.reset()
