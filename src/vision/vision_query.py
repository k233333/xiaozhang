"""云端 Vision 兜底查询

把截图 + 用户意图 + 上一步失败原因喂给视觉模型。
DeepSeek 当前不支持 vision；调用 router 的 vision_analysis 路由，按 provider 配置自动切换。
"""
from __future__ import annotations

import asyncio
import base64
import time

from src.brain.llm_router import _get_provider_client, extract_json
from src.core.config import llm_config
from src.core.logger import get_logger
from src.vision.screenshot import grab_full, to_png_bytes

log = get_logger(__name__)


VISION_SYSTEM = """你是桌面 UI 视觉分析助手。
用户提供一张截图 + 想做的事 + 上一步失败原因。
输出严格 JSON：
  {"action": "click", "x": 120, "y": 340, "reason": "..."}
  {"action": "type", "text": "...", "reason": "..."}
  {"action": "abort", "reason": "..."}
不输出任何解释文字，只输出一段 JSON。
"""


async def decide_from_screen(intent: str, last_failure: str = "") -> dict | None:
    img, _ = grab_full(save=True, tag="vision_query")
    img_bytes = to_png_bytes(img)
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{img_b64}"

    user_msg = f"用户想做：{intent}\n上一步失败原因：{last_failure or '无'}\n请看截图给出下一步动作。"

    route = llm_config.routing.get("vision_analysis")
    if route is None:
        log.error("没有 vision_analysis 路由")
        return None

    provider_cfg, model = llm_config.parse_target(route.primary)
    provider_name = route.primary.split(".", 1)[0]

    if provider_cfg.sdk != "openai":
        log.warning(
            "当前 vision provider 非 openai-sdk，跳过", provider=provider_name
        )
        return None

    loop = asyncio.get_running_loop()

    def _call() -> str:
        client = _get_provider_client(provider_name, provider_cfg)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=512,
            timeout=route.timeout,
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

    t0 = time.monotonic()
    try:
        text = await loop.run_in_executor(None, _call)
    except Exception as e:  # noqa: BLE001
        log.warning("Vision 调用失败（provider 可能不支持图片）", err=str(e))
        return None

    log.info("Vision 调用完成", elapsed_sec=round(time.monotonic() - t0, 2))
    data = extract_json(text)
    if data is None:
        return None
    log.info("Vision 决策", action=data.get("action"))
    return data
