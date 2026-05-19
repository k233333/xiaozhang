"""OmniParser 屏幕解析（v2.0 A 级第一道关）

流程：截图 → 本地 OmniParser 拿到 UI 元素列表 → 把元素表 + 用户意图喂给 LLM
LLM 输出"点哪个元素 / 输入什么"。

如果 OmniParser 未加载（被资源管理器卸载或模型缺失），调用方应直接走 vision_query.py（裸截图给 vision LLM）。
"""
from __future__ import annotations

import json
import time

from src.brain.llm_router import router
from src.core.logger import get_logger
from src.vision.screenshot import grab_full

log = get_logger(__name__)


PARSE_SYSTEM = """你是桌面 UI 视觉决策助手。
用户给你一份屏幕元素列表（OmniParser 解析）+ 用户意图 + 上一步失败原因。
列表每项：{"id": int, "type": "button|text|input|...", "text": "...", "bbox": [x1,y1,x2,y2]}

输出严格 JSON：
  {"action": "click", "id": 12, "reason": "..."}
  {"action": "type", "id": 12, "text": "...", "reason": "..."}
  {"action": "abort", "reason": "..."}
不输出任何解释文字，只输出一段 JSON。
"""


async def decide_via_omniparser(intent: str, last_failure: str = "") -> dict | None:
    from src.core.resource_manager import resource_manager  # noqa: PLC0415

    op = resource_manager.get_model("omniparser")
    if op is None:
        return None

    img, _ = grab_full(save=True, tag="omniparser")

    t0 = time.monotonic()
    try:
        elements = op.parse(img)
    except Exception as e:  # noqa: BLE001
        log.warning("OmniParser 解析失败", err=str(e))
        return None

    if not elements:
        log.info("OmniParser 解析为空，回退云端 vision")
        return None

    log.info(
        "OmniParser 解析完成",
        n_elements=len(elements),
        elapsed_sec=round(time.monotonic() - t0, 2),
    )

    user_msg = (
        f"用户意图：{intent}\n"
        f"上一步失败：{last_failure or '无'}\n"
        f"屏幕元素：\n{json.dumps(elements, ensure_ascii=False, indent=2)}"
    )
    raw = await router.complete_json(
        "vision_analysis",
        system=PARSE_SYSTEM,
        user=user_msg,
    )
    if raw is None:
        return None

    if raw.get("action") in ("click", "type"):
        eid = raw.get("id")
        if isinstance(eid, int) and 0 <= eid < len(elements):
            bbox = elements[eid].get("bbox") or [0, 0, 0, 0]
            cx = (bbox[0] + bbox[2]) // 2
            cy = (bbox[1] + bbox[3]) // 2
            raw["x"], raw["y"] = cx, cy

    return raw
