"""LLMRouter — 多 Provider 路由器（v2.0 核心）

按 task_type 找 routing 配置，按 primary -> fallback 顺序调用，每个 target 内部再 retry。
所有 provider 通过 OpenAI 兼容 SDK（DeepSeek/Qwen/Gemini/Groq 都支持）调用；
特殊 SDK（如 anthropic）走单独分支。

调用入口：
  router = LLMRouter()
  result = await router.complete("task_planning", system="...", user="...")
  obj    = await router.complete_json("task_planning", ...)

YAML 加 provider → 代码 0 改动。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from src.core.config import ProviderCfg, llm_config
from src.core.logger import get_logger

log = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ---------- Provider 客户端缓存 ----------

_clients: dict[str, object] = {}


def _get_provider_client(provider_name: str, provider: ProviderCfg) -> object:
    if provider_name in _clients:
        return _clients[provider_name]

    api_key = provider.api_key
    if not api_key:
        raise RuntimeError(f"Provider {provider_name} 缺少 env {provider.api_key_env}")

    if provider.sdk == "openai":
        from openai import OpenAI  # noqa: PLC0415

        kwargs: dict = {"api_key": api_key}
        if provider.base_url:
            kwargs["base_url"] = provider.base_url
        client = OpenAI(**kwargs)
    elif provider.sdk == "anthropic":
        from anthropic import Anthropic  # noqa: PLC0415

        kwargs = {"api_key": api_key}
        if provider.base_url:
            kwargs["base_url"] = provider.base_url
        client = Anthropic(**kwargs)
    else:
        raise ValueError(f"暂不支持的 SDK: {provider.sdk}")

    _clients[provider_name] = client
    log.info("初始化 LLM provider 客户端", provider=provider_name, sdk=provider.sdk)
    return client


# ---------- 调用核心 ----------

@dataclass
class CallResult:
    text: str
    provider: str
    model: str
    elapsed_sec: float
    cached: bool = False


def _read_prompt(name: str) -> str:
    p = PROMPTS_DIR / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _read_soul() -> str:
    p = Path(__file__).resolve().parents[2] / "config" / "soul.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _build_system(prompt_text: str | None) -> str:
    soul = _read_soul()
    if prompt_text:
        return f"{soul}\n\n---\n\n{prompt_text}".strip()
    return soul


# ---------- LRU 规划缓存 ----------

_cache: "OrderedDict[str, CallResult]" = OrderedDict()
_cache_lock = asyncio.Lock()


async def _cache_get(key: str) -> CallResult | None:
    if not llm_config.policy.cache_recent_planning:
        return None
    async with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            c = _cache[key]
            return CallResult(c.text, c.provider, c.model, 0.0, cached=True)
    return None


async def _cache_put(key: str, result: CallResult) -> None:
    if not llm_config.policy.cache_recent_planning:
        return
    async with _cache_lock:
        _cache[key] = result
        _cache.move_to_end(key)
        while len(_cache) > llm_config.policy.cache_size:
            _cache.popitem(last=False)


# ---------- JSON 抽取 ----------

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.MULTILINE)


def extract_json(text: str) -> dict | None:
    m = _CODE_BLOCK_RE.search(text)
    candidate = m.group(1) if m else text
    candidate = candidate.strip()
    if "{" in candidate and "}" in candidate:
        candidate = candidate[candidate.index("{"): candidate.rindex("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        log.error("JSON 解析失败", err=str(e), text=text[:200])
        return None


# ---------- 路由器 ----------

class LLMRouter:
    async def complete(
        self,
        task_type: str,
        *,
        system: str = "",
        user: str = "",
        max_tokens: int = 2048,
    ) -> CallResult | None:
        route = llm_config.routing.get(task_type)
        if route is None:
            log.error("未配置路由规则", task_type=task_type)
            return None

        cache_key = f"{task_type}::{user[:200]}::{system[:50]}"
        cached = await _cache_get(cache_key)
        if cached is not None:
            log.info("命中规划缓存", task_type=task_type)
            return cached

        targets: list[str] = [route.primary]
        if route.fallback:
            targets.append(route.fallback)

        last_error: str = ""
        for target in targets:
            for attempt in range(llm_config.policy.retry_max + 1):
                try:
                    result = await self._call_target(
                        target=target,
                        system=system,
                        user=user,
                        timeout=route.timeout,
                        max_tokens=max_tokens,
                    )
                    if result is not None:
                        await _cache_put(cache_key, result)
                        return result
                except Exception as e:  # noqa: BLE001
                    last_error = str(e)
                    log.warning(
                        "LLM 调用失败",
                        target=target,
                        attempt=attempt,
                        err=last_error[:200],
                    )
                    if attempt < llm_config.policy.retry_max:
                        await asyncio.sleep(llm_config.policy.retry_delay)

        log.error(
            "所有 LLM target 失败",
            task_type=task_type,
            targets=targets,
            last_error=last_error[:200],
        )
        return None

    async def complete_json(
        self,
        task_type: str,
        *,
        system: str = "",
        user: str = "",
        max_tokens: int = 2048,
    ) -> dict | None:
        result = await self.complete(task_type, system=system, user=user, max_tokens=max_tokens)
        if result is None:
            return None
        return extract_json(result.text)

    async def _call_target(
        self,
        *,
        target: str,
        system: str,
        user: str,
        timeout: int,
        max_tokens: int,
    ) -> CallResult | None:
        provider_cfg, model = llm_config.parse_target(target)
        provider_name = target.split(".", 1)[0]

        loop = asyncio.get_running_loop()
        t0 = time.monotonic()

        def _call_sync() -> str:
            client = _get_provider_client(provider_name, provider_cfg)
            if provider_cfg.sdk == "openai":
                return _openai_call(client, model, system, user, max_tokens, timeout)
            if provider_cfg.sdk == "anthropic":
                return _anthropic_call(client, model, system, user, max_tokens)
            raise ValueError(f"未支持的 SDK: {provider_cfg.sdk}")

        try:
            text = await asyncio.wait_for(
                loop.run_in_executor(None, _call_sync),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            log.warning("LLM 调用超时", target=target, timeout=timeout)
            return None

        elapsed = time.monotonic() - t0
        log.info("LLM 调用完成", target=target, elapsed_sec=round(elapsed, 2), chars=len(text))
        return CallResult(text=text, provider=provider_name, model=model, elapsed_sec=elapsed)


def _openai_call(client, model, system, user, max_tokens, timeout) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return resp.choices[0].message.content or ""


def _anthropic_call(client, model, system, user, max_tokens) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "你是一个简洁的中文助手。",
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


# 单例
router = LLMRouter()


# 旧 API 兼容
async def chat_simple(prompt_text: str, system: str = "") -> str:
    result = await router.complete(
        "simple_chat", system=_build_system(system), user=prompt_text
    )
    return result.text if result else ""


async def plan(user_text: str, *, extra_context: str = "", complex: bool = False):
    """旧 plan() API 的兼容层；返回 Plan 对象（成功）或 None

    complex=True 直接走 task_planning_complex 路由（v4-pro），用于 escalate。
    """
    from src.brain.action_schema import Plan  # noqa: PLC0415

    sys_prompt = _read_prompt("planner.md")
    user_msg = user_text
    if extra_context:
        user_msg = f"{user_text}\n\n[已知上下文]\n{extra_context}"

    task_type = "task_planning_complex" if complex else "task_planning"

    raw = await router.complete_json(
        task_type,
        system=_build_system(sys_prompt),
        user=user_msg,
    )
    if raw is None:
        return None
    try:
        return Plan.from_dict(raw)
    except Exception as e:  # noqa: BLE001
        log.error("Plan schema 校验失败", err=str(e), raw=str(raw)[:300])
        return None
