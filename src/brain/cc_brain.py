"""Claude Code 大脑模块 — 通过 llm.yaml 路由调用 LLM API。

走 llm.yaml 配置的 provider 路由（DeepSeek 主力，Groq/ccb 备用），
不硬编码任何 API endpoint。cc switch 切 provider 时小张自动跟着切。

优势：
  - 统一走 llm.yaml 路由，provider 切换 0 代码改动
  - system prompt 完全自定义（含 soul + 记忆）
  - 支持 tool_use（让 LLM 决定调哪个 xz.py 命令）
  - 本地 skill 快速路径命中时完全不调 API（0 token）

调用链路：
  用户说话 → ASR → runtime.py skill 匹配失败
  → cc_brain.chat(text) → LLM 返回要执行的命令
  → 本地执行 xz.py → 返回结果
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import get_logger

log = get_logger(__name__)

# Python 解释器（小张 venv）
PYTHON_EXE = r"D:\11111begin\xiaozhang\.venv\Scripts\python.exe"
WORK_DIR = r"D:\11111begin\xiaozhang"

# System prompt 文件
_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[2] / "config" / "ccb_system_prompt.md"
_SOUL_PATH = Path(__file__).resolve().parents[2] / "config" / "soul.md"

# 超时（秒）
API_CALL_TIMEOUT_SEC = 25
RETRY_COUNT = 2
RETRY_DELAY_SEC = 1
DEFAULT_TIMEOUT_SEC = API_CALL_TIMEOUT_SEC * (RETRY_COUNT + 1) + 10  # = 85s

# 最大输出 tokens
MAX_OUTPUT_TOKENS = 1024


@dataclass
class CCResult:
    """CC 调用结果"""
    success: bool
    reply: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_sec: float = 0.0
    model: str = ""
    commands_executed: list[str] = field(default_factory=list)


def _load_system_prompt() -> str:
    """加载 system prompt（ccb_system_prompt.md + soul.md + 记忆上下文）"""
    parts = []

    # Soul（人设）
    if _SOUL_PATH.exists():
        soul = _SOUL_PATH.read_text(encoding="utf-8").strip()
        if soul:
            parts.append(soul)

    # 核心 system prompt（命令表 + 规则）
    if _SYSTEM_PROMPT_PATH.exists():
        prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        if prompt:
            parts.append(prompt)
    else:
        parts.append(
            "你是小张桌面助手的大脑。用户说一句话，你决定执行什么桌面操作。\n"
            "回复简洁中文。如果需要执行操作，调用 execute_command 工具。"
        )

    # 用户画像
    user_profile_path = Path(WORK_DIR) / "data" / "USER.md"
    if user_profile_path.exists():
        profile = user_profile_path.read_text(encoding="utf-8").strip()
        if profile and len(profile) < 2000:
            parts.append(f"\n## 用户画像\n{profile}")

    # 最近记忆（从 memory store 拉最近几条成功会话）
    try:
        from src.memory import store  # noqa: PLC0415
        recent = store.recent_sessions(limit=5)
        if recent:
            memory_lines = []
            for s in recent:
                if s.get("success") and s.get("user_text"):
                    intent = s.get("intent", "")
                    text = s.get("user_text", "")[:40]
                    memory_lines.append(f"- \"{text}\" → {intent}")
            if memory_lines:
                parts.append(f"\n## 最近成功的任务（参考）\n" + "\n".join(memory_lines[:5]))
    except Exception:
        pass

    return "\n\n---\n\n".join(parts)


# ---------- Tools 定义（让 LLM 决定调哪个命令）----------

TOOLS = [
    {
        "name": "execute_command",
        "description": "在小张的电脑上执行 xz.py 桌面操作命令",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "要执行的 xz.py 子命令，例如：\n"
                        "- open-app chrome\n"
                        "- system screenshot\n"
                        "- media play-pause\n"
                        "- douyin-search 不惑兄弟\n"
                        "- bilibili-search 原神攻略\n"
                        "- search-torrent White Lotus S03\n"
                        "- chrome-click 播放按钮\n"
                        "- screen-click 文件菜单\n"
                        "- news tech\n"
                        "- skill-list"
                    ),
                }
            },
            "required": ["command"],
        },
    }
]


def _get_api_config() -> tuple[str, str, str]:
    """从 llm.yaml 获取当前 API 配置。

    优先级：ccb > deepseek > groq
    返回 (base_url, api_key, model)
    """
    from src.core.config import llm_config  # noqa: PLC0415

    # 尝试 ccb（gpt-5.5，最强）
    try:
        ccb_cfg = llm_config.providers.get("ccb")
        if ccb_cfg:
            key = ccb_cfg.api_key
            if key:
                return ccb_cfg.base_url, key, "gpt-5.5"
    except Exception:
        pass

    # 尝试 deepseek（稳定主力）
    try:
        ds_cfg = llm_config.providers.get("deepseek")
        if ds_cfg:
            key = ds_cfg.api_key
            if key:
                return ds_cfg.base_url, key, "deepseek-chat"
    except Exception:
        pass

    # 尝试 groq（免费备用）
    try:
        groq_cfg = llm_config.providers.get("groq")
        if groq_cfg:
            key = groq_cfg.api_key
            if key:
                return groq_cfg.base_url, key, "llama-3.3-70b-versatile"
    except Exception:
        pass

    raise RuntimeError("llm.yaml 中没有可用的 provider（需要 ccb/deepseek/groq 之一有 API key）")


async def chat(user_text: str, *, timeout: int = DEFAULT_TIMEOUT_SEC) -> CCResult:
    """调用 LLM 处理用户输入。

    流程：
    1. 发送用户文本 + system prompt + tools 给 API
    2. 如果 LLM 返回 tool_use → 执行 xz.py 命令 → 返回结果给 LLM
    3. LLM 生成最终回复
    """
    system_prompt = _load_system_prompt()

    log.info("CC 调用开始", text=user_text[:50], timeout=timeout)
    t0 = time.monotonic()

    # 气泡状态更新
    try:
        from src.ui.toast import show_status  # noqa: PLC0415
        show_status("正在调用 AI…")
    except Exception:
        pass

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _call_api_with_tools, user_text, system_prompt),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        log.error("CC 调用超时", elapsed_sec=round(elapsed, 1))
        return CCResult(success=False, reply="CC 调用超时", duration_sec=elapsed)
    except Exception as e:
        elapsed = time.monotonic() - t0
        log.error("CC 调用异常", err=str(e), elapsed_sec=round(elapsed, 1))
        return CCResult(success=False, reply=f"CC 调用失败: {e}", duration_sec=elapsed)

    result.duration_sec = time.monotonic() - t0

    log.info(
        "CC 调用完成",
        success=result.success,
        elapsed_sec=round(result.duration_sec, 1),
        in_tok=result.input_tokens,
        out_tok=result.output_tokens,
        cmds=result.commands_executed,
    )

    # Token 追踪
    if result.input_tokens or result.output_tokens:
        try:
            from src.core.token_tracker import tracker  # noqa: PLC0415
            tracker.record(
                provider="cc_brain",
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_hit_tokens=0,
            )
        except Exception:
            pass

    return result


def _call_api_with_tools(user_text: str, system_prompt: str) -> CCResult:
    """同步调用 API（支持 tool_use 循环，自动 fallback 多 provider）"""
    import httpx

    # 获取 provider 列表（按优先级尝试）
    providers = _get_provider_list()

    for provider_name, base_url, api_key, model in providers:
        try:
            result = _try_provider(
                provider_name, base_url, api_key, model,
                user_text, system_prompt,
            )
            if result is not None:
                return result
        except Exception as e:
            log.warning("Provider 失败，尝试下一个", provider=provider_name, err=str(e)[:100])
            continue

    return CCResult(
        success=False,
        reply="所有 LLM provider 均不可用",
        model="none",
    )


def _get_provider_list() -> list[tuple[str, str, str, str]]:
    """返回 [(name, base_url, api_key, model), ...] 按优先级排序"""
    from src.core.config import llm_config  # noqa: PLC0415

    result = []

    # 优先 ccb（gpt-5.5 最强，支持 tool_use）
    try:
        ccb = llm_config.providers.get("ccb")
        if ccb and ccb.api_key:
            result.append(("ccb", ccb.base_url, ccb.api_key, "gpt-5.5"))
    except Exception:
        pass

    # DeepSeek（稳定，便宜，但不支持 Anthropic tool_use 格式）
    # DeepSeek 走 OpenAI 格式的 function calling
    try:
        ds = llm_config.providers.get("deepseek")
        if ds and ds.api_key:
            result.append(("deepseek", ds.base_url, ds.api_key, "deepseek-chat"))
    except Exception:
        pass

    # Groq（免费但 TPM 限制）
    try:
        groq = llm_config.providers.get("groq")
        if groq and groq.api_key:
            result.append(("groq", groq.base_url, groq.api_key, "llama-3.3-70b-versatile"))
    except Exception:
        pass

    return result


def _try_provider(
    provider_name: str,
    base_url: str,
    api_key: str,
    model: str,
    user_text: str,
    system_prompt: str,
) -> CCResult | None:
    """尝试用一个 provider 完成 tool_use 循环"""
    import httpx

    # 统一用 OpenAI 兼容格式（DeepSeek / ccb / Groq 都支持）
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 构建 OpenAI 格式的 tools
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": TOOLS[0]["description"],
                "parameters": TOOLS[0]["input_schema"],
            }
        }
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    total_input = 0
    total_output = 0
    commands_executed = []

    # Tool use 循环（最多 5 轮）
    for turn in range(5):
        body = {
            "model": model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": messages,
            "tools": openai_tools,
        }

        # 重试
        last_err = ""
        data = None
        for attempt in range(RETRY_COUNT + 1):
            try:
                with httpx.Client(timeout=API_CALL_TIMEOUT_SEC) as client:
                    resp = client.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                    resp.raise_for_status()
                    raw = resp.text.strip()
                    if not raw:
                        last_err = f"API 返回空响应 (attempt {attempt+1})"
                        log.warning("API 空响应，重试", provider=provider_name, attempt=attempt+1)
                        import time as _t; _t.sleep(RETRY_DELAY_SEC)
                        continue
                    data = resp.json()
                    break
            except httpx.HTTPStatusError as e:
                last_err = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                log.warning("API HTTP 错误", provider=provider_name, status=e.response.status_code)
                import time as _t; _t.sleep(RETRY_DELAY_SEC)
            except Exception as e:
                last_err = f"网络错误: {e}"
                log.warning("API 网络错误", provider=provider_name, err=str(e)[:100])
                import time as _t; _t.sleep(RETRY_DELAY_SEC)

        if data is None:
            log.warning("Provider 全部重试失败", provider=provider_name, err=last_err[:100])
            return None  # 让外层尝试下一个 provider

        # 累计 token
        usage = data.get("usage", {})
        total_input += usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        total_output += usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)

        # 解析 choice
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "")

        # 没有 tool_calls → 直接返回文本
        tool_calls = message.get("tool_calls")
        if not tool_calls or finish_reason == "stop":
            reply = (message.get("content") or "").strip()
            return CCResult(
                success=bool(reply),
                reply=reply or "已完成",
                input_tokens=total_input,
                output_tokens=total_output,
                model=model,
                commands_executed=commands_executed,
            )

        # 有 tool_calls → 执行命令
        messages.append(message)  # assistant message with tool_calls

        for tc in tool_calls:
            func = tc.get("function", {})
            tc_id = tc.get("id", "")
            func_name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            if func_name == "execute_command":
                command = args.get("command", "")
                if command:
                    commands_executed.append(command)
                    log.info("执行 xz.py 命令", cmd=command, turn=turn, provider=provider_name)
                    try:
                        from src.ui.toast import show_status  # noqa: PLC0415
                        show_status(f"执行: {command[:40]}")
                    except Exception:
                        pass
                    cmd_result = _execute_xz_command(command)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": cmd_result[:2000],
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": "错误：空命令",
                    })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"未知工具: {func_name}",
                })

    # 超过 5 轮
    return CCResult(
        success=False,
        reply="执行轮次过多，已停止",
        input_tokens=total_input,
        output_tokens=total_output,
        model=model,
        commands_executed=commands_executed,
    )


def _execute_xz_command(command: str) -> str:
    """执行 xz.py 命令并返回 stdout"""
    full_cmd = f'"{PYTHON_EXE}" "{WORK_DIR}\\xz.py" {command}'

    env = os.environ.copy()
    venv_scripts = str(Path(PYTHON_EXE).parent)
    if venv_scripts not in env.get("PATH", ""):
        env["PATH"] = f"{venv_scripts};{env.get('PATH', '')}"

    try:
        proc = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            cwd=WORK_DIR,
            env=env,
        )
        output = proc.stdout.strip()
        if proc.returncode != 0 and proc.stderr:
            output += f"\n[STDERR] {proc.stderr.strip()[:500]}"
        return output or f"(exit code {proc.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return "[TIMEOUT] 命令执行超过 20 秒"
    except Exception as e:
        return f"[ERROR] {e}"


# ---------- 便捷函数 ----------

async def is_available() -> bool:
    """检查是否有任何可用的 LLM provider"""
    try:
        providers = _get_provider_list()
        return len(providers) > 0
    except Exception:
        return False
