"""Silero VAD（ONNX）

Silero v5 ONNX 输入：
  - input: float32 [1, N]，N 应该是 32ms (512 samples @ 16kHz) 倍数
  - state: float32 [2, 1, 128]
  - sr:    int64 标量 16000
输出：
  - output: float32 [1, 1] 置信度
  - stateN: 新 state
"""
from __future__ import annotations

import numpy as np

from src.core.config import LocalModelCfg, settings
from src.core.logger import get_logger
from src.local_models.base import LocalModel

log = get_logger(__name__)


class SileroVadModel(LocalModel):
    name = "silero_vad"

    def __init__(self, cfg: LocalModelCfg) -> None:
        super().__init__(cfg)
        self._state: np.ndarray | None = None
        self._sr_input: np.ndarray | None = None

    def _load(self) -> None:
        super()._load()
        self.reset_state()

    def reset_state(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._sr_input = np.array(settings.audio.sample_rate, dtype=np.int64)

    def is_speech(self, samples_int16: np.ndarray) -> float:
        if not self._loaded or self._session is None:
            return 0.0
        if samples_int16.dtype != np.float32:
            audio = (samples_int16.astype(np.float32) / 32768.0).reshape(1, -1)
        else:
            audio = samples_int16.reshape(1, -1)
        try:
            ort_inputs = {"input": audio, "state": self._state, "sr": self._sr_input}
            out, new_state = self._session.run(None, ort_inputs)
            self._state = new_state
            return float(out.flatten()[0])
        except Exception as e:  # noqa: BLE001
            log.debug("Silero VAD 推理失败", err=str(e))
            return 0.0
