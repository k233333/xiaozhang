"""截图工具

用 mss 做整屏 / 区域 / 当前活动窗口截图。
图像保存到 logs/screenshots/，每张文件名含 trace_id 便于追溯。
"""
from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import mss
from PIL import Image

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


def _shots_dir() -> Path:
    p = settings.resolve_path(settings.paths.logs_dir) / "screenshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def grab_full(save: bool = True, tag: str = "") -> tuple[Image.Image, Path | None]:
    """整屏截图。返回 (PIL.Image, 保存路径)"""
    with mss.MSS() as sct:
        # mss 第 0 个 monitor 是所有屏拼接，第 1 个开始是单屏
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    saved = None
    if save:
        ts = time.strftime("%Y%m%d-%H%M%S")
        fname = f"{ts}_{tag or 'full'}.png"
        saved = _shots_dir() / fname
        img.save(saved, "PNG", optimize=True)
        log.info("截图保存", path=str(saved), size=img.size)
    return img, saved


def grab_region(left: int, top: int, width: int, height: int, save: bool = True, tag: str = "") -> tuple[Image.Image, Path | None]:
    with mss.MSS() as sct:
        raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    saved = None
    if save:
        ts = time.strftime("%Y%m%d-%H%M%S")
        fname = f"{ts}_{tag or 'region'}.png"
        saved = _shots_dir() / fname
        img.save(saved, "PNG", optimize=True)
    return img, saved


def to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
