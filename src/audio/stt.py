"""中文 ASR 转写（v3.0）

优先级：
  1. 豆包 ASR（云端，中文口语最强，~0.5-1s）
  2. SenseVoice-Small（DirectML GPU，60s 后加载，<1s）
  3. faster-whisper small（CPU fallback，1-2s）

豆包 ASR 失败时自动降级，不影响主流程。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import numpy as np

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class Transcript:
    text: str
    language: str
    duration_sec: float
    elapsed_sec: float
    backend: str = ""


# ---- faster-whisper fallback ----

_fw_model: object | None = None
_fw_lock = asyncio.Lock()

# faster-whisper 硬编码参数（只是 fallback，不需要用户配置）
_FW_MODEL_SIZE = "small"
_FW_DEVICE = "cpu"
_FW_COMPUTE = "int8"
_FW_LANGUAGE = "zh"
_FW_BEAM = 5


def _load_fw() -> object:
    from faster_whisper import WhisperModel  # noqa: PLC0415

    log.info("加载 faster-whisper（fallback）", size=_FW_MODEL_SIZE, device=_FW_DEVICE)
    t0 = time.monotonic()
    model = WhisperModel(_FW_MODEL_SIZE, device=_FW_DEVICE, compute_type=_FW_COMPUTE)
    log.info("faster-whisper 加载完成", elapsed_sec=round(time.monotonic() - t0, 2))
    return model


async def _get_fw_model():
    global _fw_model
    if _fw_model is not None:
        return _fw_model
    async with _fw_lock:
        if _fw_model is None:
            loop = asyncio.get_running_loop()
            _fw_model = await loop.run_in_executor(None, _load_fw)
    return _fw_model


def _to_float32_16k(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32) / 32768.0
    if sample_rate != 16000:
        ratio = 16000 / sample_rate
        new_len = int(len(samples) * ratio)
        idx = np.linspace(0, len(samples) - 1, new_len).astype(np.int64)
        samples = samples[idx]
    return samples


# ---- 主接口 ----

async def transcribe(samples: np.ndarray, sample_rate: int) -> Transcript | None:
    """异步转写。优先豆包 ASR，其次 SenseVoice GPU，最后 faster-whisper CPU。"""
    duration = len(samples) / sample_rate
    if duration < 0.3:
        log.info("音频太短，跳过转写", duration=duration)
        return None

    # 1. 豆包 ASR（最高优先级，中文口语最强）
    try:
        from src.audio.stt_doubao import transcribe as doubao_transcribe  # noqa: PLC0415
        text = await doubao_transcribe(samples, sample_rate)
        if text:
            return Transcript(
                text=text,
                language="zh",
                duration_sec=duration,
                elapsed_sec=0.0,
                backend="doubao",
            )
    except Exception as e:
        log.debug("豆包 ASR 跳过", err=str(e))

    # 2. SenseVoice GPU
    text, backend = await _try_sensevoice(samples, sample_rate)
    if text:
        return Transcript(
            text=text,
            language="zh",
            duration_sec=duration,
            elapsed_sec=0.0,
            backend=backend,
        )

    # 3. faster-whisper CPU fallback
    return await _transcribe_fw(samples, sample_rate, duration)


async def _try_sensevoice(samples: np.ndarray, sample_rate: int) -> tuple[str, str]:
    try:
        from src.core.resource_manager import resource_manager  # noqa: PLC0415
    except Exception:
        return "", ""
    sv = resource_manager.get_model("sensevoice")
    if sv is None or not sv.is_loaded():
        return "", ""

    audio = samples
    if sample_rate != 16000:
        ratio = 16000 / sample_rate
        new_len = int(len(samples) * ratio)
        idx = np.linspace(0, len(samples) - 1, new_len).astype(np.int64)
        audio = samples[idx]

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    text = await loop.run_in_executor(None, lambda: sv.transcribe(audio, 16000))
    log.info(
        "SenseVoice 转写完成",
        chars=len(text),
        elapsed_sec=round(time.monotonic() - t0, 2),
    )
    return text, "sensevoice"


async def _transcribe_fw(
    samples: np.ndarray, sample_rate: int, duration: float
) -> Transcript | None:
    audio = _to_float32_16k(samples, sample_rate)
    model = await _get_fw_model()

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()

    def _do():
        segments, info = model.transcribe(  # type: ignore[attr-defined]
            audio,
            language=_FW_LANGUAGE,
            beam_size=_FW_BEAM,
            vad_filter=False,
        )
        parts = []
        for seg in segments:
            parts.append(seg.text)
        return "".join(parts).strip(), info.language

    text, lang = await loop.run_in_executor(None, _do)
    elapsed = time.monotonic() - t0
    log.info("faster-whisper 转写完成", text=text[:60], elapsed_sec=round(elapsed, 2))
    return Transcript(
        text=text,
        language=lang,
        duration_sec=duration,
        elapsed_sec=elapsed,
        backend="faster-whisper",
    )


async def warm_up() -> None:
    """启动时预热（如果 SenseVoice 已加载就不预热 faster-whisper）"""
    try:
        from src.core.resource_manager import resource_manager  # noqa: PLC0415
        if resource_manager.get_model("sensevoice") is not None:
            return
    except Exception:  # noqa: BLE001
        pass
    await _get_fw_model()
