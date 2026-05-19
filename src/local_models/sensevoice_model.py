"""SenseVoice-Small 中文 ASR

主路径：funasr AutoModel；裸 ONNX 留给 D8 阶段补完整管线。
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from src.core.config import LocalModelCfg
from src.core.logger import get_logger
from src.local_models.base import LocalModel

log = get_logger(__name__)


_TOKENS_TO_STRIP = [
    "<|zh|>", "<|en|>", "<|yue|>", "<|ja|>", "<|ko|>",
    "<|NEUTRAL|>", "<|HAPPY|>", "<|SAD|>", "<|ANGRY|>",
    "<|Speech|>", "<|BGM|>", "<|withitn|>", "<|woitn|>", "<|nospeech|>",
]


class SenseVoiceModel(LocalModel):
    name = "sensevoice"

    def __init__(self, cfg: LocalModelCfg) -> None:
        super().__init__(cfg)
        self._tokenizer: Any = None

    def _load(self) -> None:
        # 优先 funasr
        try:
            from funasr import AutoModel  # noqa: PLC0415

            self._session = AutoModel(
                model="iic/SenseVoiceSmall",
                model_revision="master",
                device="cpu",
                disable_update=True,
            )
            log.info("SenseVoice via funasr 加载完成")
            return
        except Exception as e:  # noqa: BLE001
            log.debug("funasr 加载失败，尝试裸 ONNX", err=str(e))
        # 兜底：裸 ONNX（需要用户准备好模型）
        super()._load()

    def transcribe(self, audio_int16: np.ndarray, sample_rate: int = 16000) -> str:
        if not self._loaded:
            return ""
        t0 = time.monotonic()
        try:
            if hasattr(self._session, "generate"):
                audio = audio_int16.astype(np.float32) / 32768.0
                res = self._session.generate(
                    input=audio, cache={}, language="zh", use_itn=True,
                )
                text = res[0].get("text", "") if res else ""
                for tok in _TOKENS_TO_STRIP:
                    text = text.replace(tok, "")
                text = text.strip()
            else:
                log.warning("裸 ONNX SenseVoice 推理尚未实现")
                text = ""
            log.info(
                "SenseVoice 转写完成",
                chars=len(text),
                elapsed_sec=round(time.monotonic() - t0, 2),
            )
            return text
        except Exception as e:  # noqa: BLE001
            log.exception("SenseVoice 推理失败", err=str(e))
            return ""
