"""云端 Vision 兜底查询（v2.0 H 选项 — 多 provider 真视觉）

调用流程：
  1. 走 routing.vision_analysis.primary
  2. 如果 provider.supports_vision = True → 真发截图给 vision API
  3. 如果 provider 不支持 vision（如 deepseek） → fallback 到"盲规划"
     （仅发 intent + 失败原因，让模型基于通用知识猜下一步）
  4. 任意 provider key 缺失或失败 → 自动 fallback 到 routing 的 fallback 项

支持 SDK：
  - openai 兼容（DashScope/Gemini/OpenRouter/OpenAI 都用同一格式）
  - anthropic 原生（Claude）
"""
from __future__ import annotations

import asyncio
import base64
import time

from src.brain.llm_router import _get_provider_client, extract_json
from src.core.config import ProviderCfg, llm_config
from src.core.logger import get_logger
from src.vision.screenshot import grab_full, to_png_bytes

log = get_logger(__name__)


VISION_SYSTEM = """你是桌面 UI 视觉分析助手。
用户提供一张屏幕截图 + 想做的事 + 上一步失败原因。
你需要在截图中定位用户要的目标，输出严格 JSON：

  {"action": "click", "x": 120, "y": 340, "reason": "点了开始按钮"}
  {"action": "type", "text": "...", "reason": "输入到搜索框"}
  {"action": "abort", "reason": "屏幕上没有该元素"}

坐标系是屏幕像素，左上角 (0,0)。x/y 是要点击位置的中心。
不输出任何解释文字、不输出 markdown，只输出一段 JSON。"""


BLIND_SYSTEM = """你是桌面 UI 决策助手（无视觉模式）。
用户告诉你想做什么 + 上一步为何失败，但你看不到屏幕。
你只能基于通用知识推测下一步通用动作（如"按 Tab 键切焦点"、"按 Enter 确认"），
或者明确放弃让用户自己接手。

输出严格 JSON，action 限于：keys / type / abort
  {"action": "keys", "keys": "tab", "reason": "..."}
  {"action": "type", "text": "...", "reason": "..."}
  {"action": "abort", "reason": "需要视觉才能定位"}
不输出任何解释，只输出 JSON。"""


async def decide_from_screen(intent: str, last_failure: str = "") -> dict | None:
    """主入口：尝试 primary，失败则 fallback"""
    route = llm_config.routing.get("vision_analysis")
    if route is None:
        log.error("没有 vision_analysis 路由")
        return None

    targets: list[str] = [route.primary]
    if route.fallback:
        targets.append(route.fallback)

    last_err = ""
    for target in targets:
        try:
            provider_cfg, model = llm_config.parse_target(target)
        except (KeyError, ValueError) as e:
            last_err = f"路由解析 {target} 失败：{e}"
            log.warning(last_err)
            continue

        provider_name = target.split(".", 1)[0]

        # 检查 key 是否就绪
        if not provider_cfg.api_key:
            last_err = f"{provider_name} 缺少 env {provider_cfg.api_key_env}"
            log.warning("vision provider 跳过", reason=last_err)
            continue

        result = await _try_target(
            provider_name=provider_name,
            provider_cfg=provider_cfg,
            model=model,
            timeout=route.timeout,
            intent=intent,
            last_failure=last_failure,
        )
        if result is not None:
            return result

    log.error("vision_analysis 全部目标失败", last_err=last_err[:200])
    return None


async def _try_target(
    *,
    provider_name: str,
    provider_cfg: ProviderCfg,
    model: str,
    timeout: int,
    intent: str,
    last_failure: str,
) -> dict | None:
    """对单个 target 尝试 vision 或盲规划"""
    use_vision = provider_cfg.supports_vision

    if use_vision:
        return await _call_with_image(
            provider_name=provider_name,
            provider_cfg=provider_cfg,
            model=model,
            timeout=timeout,
            intent=intent,
            last_failure=last_failure,
        )
    else:
        log.info(
            "provider 不支持 vision，走盲规划模式",
            provider=provider_name,
            model=model,
        )
        return await _call_blind(
            provider_name=provider_name,
            provider_cfg=provider_cfg,
            model=model,
            timeout=timeout,
            intent=intent,
            last_failure=last_failure,
        )


async def _call_with_image(
    *,
    provider_name: str,
    provider_cfg: ProviderCfg,
    model: str,
    timeout: int,
    intent: str,
    last_failure: str,
) -> dict | None:
    """真视觉调用 — 截图 → base64 → vision API"""
    img, _ = grab_full(save=True, tag="vision_query")
    img_bytes = to_png_bytes(img)
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    user_msg = (
        f"用户想做：{intent}\n"
        f"上一步失败原因：{last_failure or '无'}\n"
        f"屏幕分辨率：{img.size[0]}x{img.size[1]}\n"
        f"请看截图给出下一步动作。"
    )

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()

    def _call() -> str:
        client = _get_provider_client(provider_name, provider_cfg)
        if provider_cfg.sdk == "openai":
            return _openai_vision(client, model, user_msg, img_b64, timeout)
        if provider_cfg.sdk == "anthropic":
            return _anthropic_vision(client, model, user_msg, img_b64)
        raise ValueError(f"暂不支持的 SDK: {provider_cfg.sdk}")

    try:
        text = await asyncio.wait_for(
            loop.run_in_executor(None, _call), timeout=timeout
        )
    except asyncio.TimeoutError:
        log.warning("Vision 调用超时", provider=provider_name, timeout=timeout)
        return None
    except Exception as e:  # noqa: BLE001
        log.warning("Vision 调用失败", provider=provider_name, err=str(e)[:200])
        return None

    log.info(
        "Vision 调用完成",
        provider=provider_name,
        model=model,
        elapsed_sec=round(time.monotonic() - t0, 2),
        chars=len(text),
    )
    data = extract_json(text)
    if data is None:
        return None
    log.info("Vision 决策", provider=provider_name, action=data.get("action"))
    return data


async def _call_blind(
    *,
    provider_name: str,
    provider_cfg: ProviderCfg,
    model: str,
    timeout: int,
    intent: str,
    last_failure: str,
) -> dict | None:
    """盲规划：不发图，让模型基于通用知识猜下一步"""
    user_msg = (
        f"用户想做：{intent}\n"
        f"上一步失败原因：{last_failure or '无'}\n"
        f"我看不到屏幕，请基于通用知识推测下一步通用动作（按键/输入），或 abort。"
    )

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()

    def _call() -> str:
        client = _get_provider_client(provider_name, provider_cfg)
        if provider_cfg.sdk != "openai":
            raise NotImplementedError(f"盲规划暂不支持 sdk={provider_cfg.sdk}")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=256,
            timeout=timeout,
            messages=[
                {"role": "system", "content": BLIND_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        return resp.choices[0].message.content or ""

    try:
        text = await asyncio.wait_for(
            loop.run_in_executor(None, _call), timeout=timeout
        )
    except Exception as e:  # noqa: BLE001
        log.warning("盲规划调用失败", err=str(e)[:200])
        return None

    log.info(
        "盲规划完成",
        provider=provider_name,
        elapsed_sec=round(time.monotonic() - t0, 2),
    )
    return extract_json(text)


# ---------- SDK 层 ----------

def _openai_vision(client, model: str, user_msg: str, img_b64: str, timeout: int) -> str:
    """OpenAI 兼容协议（DashScope / Gemini OpenAI 兼容端 / OpenRouter / 真 OpenAI）"""
    data_url = f"data:image/png;base64,{img_b64}"
    resp = client.chat.completions.create(
        model=model,
        max_tokens=2048,  # Gemini 2.5 是 reasoning model，需要给思考 token 留空间
        timeout=timeout,
        messages=[
            {"role": "system", "content": VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": user_msg},
                ],
            },
        ],
    )
    return resp.choices[0].message.content or ""


def _anthropic_vision(client, model: str, user_msg: str, img_b64: str) -> str:
    """Anthropic 原生格式"""
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=VISION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": user_msg},
                ],
            }
        ],
    )
    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)
