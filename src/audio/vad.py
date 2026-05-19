"""VAD 抽象层：优先 Silero，回退 webrtcvad"""
from __future__ import annotations

from typing import Protocol

import numpy as np

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


class _VadBackend(Protocol):
    def is_speech(self, frame: np.ndarray) -> bool:
        ...


class WebRtcVad:
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000) -> None:
        try:
            import webrtcvad  # noqa: PLC0415
            self._vad = webrtcvad.Vad(aggressiveness)
            self._sr = sample_rate
            log.info("webrtcvad 就绪", aggressiveness=aggressiveness)
        except Exception as e:  # noqa: BLE001
            log.warning("webrtcvad 不可用", err=str(e))
            self._vad = None
            self._sr = sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        if self._vad is None:
            rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
            return rms > 500.0
        try:
            return self._vad.is_speech(frame.tobytes(), self._sr)
        except Exception:  # noqa: BLE001
            return False


class SileroAdapter:
    def __init__(self, model) -> None:
        self.model = model
        self.threshold = settings.vad.silero_threshold

    def is_speech(self, frame: np.ndarray) -> bool:
        if frame.size == 0 or not self.model.is_loaded():
            return False
        if frame.size != 512:
            target = ((frame.size + 511) // 512) * 512
            padded = np.zeros(target, dtype=frame.dtype)
            padded[: frame.size] = frame
            frame = padded
        score = self.model.is_speech(frame)
        return score >= self.threshold


def get_vad() -> _VadBackend:
    try:
        from src.core.resource_manager import resource_manager  # noqa: PLC0415
        m = resource_manager.get_model("silero_vad")
        if m is not None and m.is_loaded():
            return SileroAdapter(m)
    except Exception:  # noqa: BLE001
        pass
    return WebRtcVad(
        aggressiveness=settings.vad.aggressiveness,
        sample_rate=settings.audio.sample_rate,
    )
