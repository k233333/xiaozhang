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
        """加载自训练唤醒词模型（sklearn ONNX 分类器，不走 openWakeWord Model）"""
        from src.audio.wake_word_custom import _load as custom_load, is_loaded  # noqa: PLC0415

        if is_loaded():
            self._oww = True  # 标记已加载
            self._session = True
            return

        ok = custom_load()
        if ok:
            self._oww = True
            self._session = True
        else:
            raise RuntimeError("xiaozhang_wakeword.onnx 加载失败（检查模型和配置文件）")

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
