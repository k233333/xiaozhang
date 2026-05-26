# coding: utf-8
"""RapidOCR 本地模型（PaddleOCR ONNX，全 DirectML）

注册到 resource_manager，开机时跟其他模型一起预加载到显存。
screen_parser 通过 resource_manager.get_model("rapidocr") 获取已加载实例。
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.core.config import LocalModelCfg
from src.core.logger import get_logger
from src.local_models.base import LocalModel

log = get_logger(__name__)


class RapidOCRModel(LocalModel):
    name = "rapidocr"

    def __init__(self, cfg: LocalModelCfg) -> None:
        super().__init__(cfg)
        self._ocr: Any = None

    def load(self) -> bool:
        """覆盖 base.load()：RapidOCR 自带内置模型，不需要检查 model_path。"""
        if self._loaded:
            return True
        try:
            self._load()
            self._loaded = True
            log.info("本地模型已加载", name=self.name, providers=self.providers)
            return True
        except Exception as e:  # noqa: BLE001
            log.exception("本地模型加载失败", name=self.name, err=str(e))
            return False

    def _load(self) -> None:
        """加载 RapidOCR，三个 session 全走 DirectML。"""
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
        except ImportError as e:
            raise ImportError("rapidocr_onnxruntime 未装。装：uv pip install rapidocr-onnxruntime") from e

        use_dml = "DmlExecutionProvider" in (self.providers or [])
        self._ocr = RapidOCR(
            det_use_dml=use_dml,
            rec_use_dml=use_dml,
            cls_use_dml=use_dml,
        )
        # 标记 session 存在（base.py 用 self._session 判断 loaded）
        self._session = self._ocr
        log.info("RapidOCR 加载成功", use_dml=use_dml)

    def _unload(self) -> None:
        del self._ocr
        self._ocr = None

    def ocr(self, img: np.ndarray) -> list[tuple[list[int], str, float]]:
        """OCR 推理。返回 [([x1,y1,x2,y2], text, conf), ...]"""
        if self._ocr is None:
            return []
        try:
            results, _elapsed = self._ocr(img)
        except Exception as e:
            log.warning("RapidOCR 推理异常", err=str(e))
            return []
        if not results:
            return []
        out: list[tuple[list[int], str, float]] = []
        for item in results:
            box, text, conf = item[0], item[1], item[2]
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            text = (text or "").strip()
            if not text:
                continue
            out.append(([x1, y1, x2, y2], text, float(conf)))
        return out
