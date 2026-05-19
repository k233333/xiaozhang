"""OmniParser-v2 屏幕元素解析（占位骨架，D8-9 阶段补完整推理）"""
from __future__ import annotations

import time
from typing import Any

from PIL import Image

from src.core.config import LocalModelCfg
from src.core.logger import get_logger
from src.local_models.base import LocalModel

log = get_logger(__name__)


class OmniParserModel(LocalModel):
    name = "omniparser"

    def __init__(self, cfg: LocalModelCfg) -> None:
        super().__init__(cfg)
        self._yolo: Any = None
        self._caption: Any = None

    def _load(self) -> None:
        if not self.model_path.is_dir():
            log.warning("OmniParser 模型目录不存在", path=str(self.model_path))
            raise FileNotFoundError(self.model_path)

        import onnxruntime as ort  # noqa: PLC0415

        yolo_path = self.model_path / "icon_detect" / "model.onnx"
        if yolo_path.exists():
            self._yolo = ort.InferenceSession(str(yolo_path), providers=self.providers)
            log.info("OmniParser YOLO 已加载", path=str(yolo_path))
        else:
            log.warning("icon_detect 缺失", path=str(yolo_path))

        caption_path = self.model_path / "icon_caption" / "model.onnx"
        if caption_path.exists():
            self._caption = ort.InferenceSession(str(caption_path), providers=self.providers)
            log.info("OmniParser Caption 已加载", path=str(caption_path))
        else:
            log.debug("caption 缺失（可选）", path=str(caption_path))

        self._session = self._yolo

    def parse(self, image: Image.Image) -> list[dict]:
        if not self._loaded or self._yolo is None:
            return []
        t0 = time.monotonic()
        # YOLO 真实推理（letterbox + normalize + NMS）放在 D8-9 实现
        log.info(
            "OmniParser 推理（占位）",
            image_size=image.size,
            elapsed_sec=round(time.monotonic() - t0, 2),
        )
        return []

    def _unload(self) -> None:
        if self._yolo is not None:
            del self._yolo
            self._yolo = None
        if self._caption is not None:
            del self._caption
            self._caption = None
