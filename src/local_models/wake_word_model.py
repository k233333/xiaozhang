"""唤醒词模型（基于 openwakeword 框架，底层 ONNX）"""
from __future__ import annotations

from typing import Any

from src.core.config import LocalModelCfg
from src.core.logger import get_logger
from src.local_models.base import LocalModel

log = get_logger(__name__)


class WakeWordModel(LocalModel):
    name = "wake_word"

    def __init__(self, cfg: LocalModelCfg) -> None:
        super().__init__(cfg)
        self._oww: Any = None

    def _load(self) -> None:
        from openwakeword.model import Model  # noqa: PLC0415

        custom_models: list[str] = []
        if self.model_path.is_file():
            custom_models = [str(self.model_path)]
        elif self.model_path.is_dir():
            custom_models = [
                str(p) for p in self.model_path.glob("*.onnx")
            ] + [str(p) for p in self.model_path.glob("*.tflite")]

        if not custom_models:
            log.warning(
                "未找到自训练唤醒词，使用 openWakeWord 默认（仅英文）",
                model_dir=str(self.model_path),
            )
            self._oww = Model(inference_framework="onnx")
        else:
            self._oww = Model(
                wakeword_models=custom_models,
                inference_framework="onnx",
            )
        self._session = self._oww

    def predict(self, audio_int16) -> dict[str, float]:
        if not self._loaded or self._oww is None:
            return {}
        return self._oww.predict(audio_int16)

    def reset(self) -> None:
        if self._oww is not None:
            try:
                self._oww.reset()
            except Exception:  # noqa: BLE001
                pass
