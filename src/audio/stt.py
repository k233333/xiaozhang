"""faster-whisper 转写

模型按需加载（首次调用才下载/初始化），常驻一个全局实例。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import numpy as np

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

# 全局模型实例（懒加载）
_model: object | None = None
_model_lock = asyncio.Lock()


@dataclass
class Transcript:
    text: str
    language: str
    duration_sec: float
    elapsed_sec: float
    avg_logprob: float | None = None


def _load_model():
    """同步加载 faster-whisper 模型。耗时 5-30 秒。"""
    from faster_whisper import WhisperModel  # noqa: PLC0415

    log.info(
        "加载 faster-whisper 模型",
        size=settings.stt.model_size,
        device=settings.stt.device,
        compute=settings.stt.compute_type,
    )
    t0 = time.monotonic()
    model = WhisperModel(
        settings.stt.model_size,
        device=settings.stt.device,
        compute_type=settings.stt.compute_type,
    )
    log.info("模型加载完成", elapsed_sec=round(time.monotonic() - t0, 2))
    return model


async def get_model():
    global _model
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is None:
            loop = asyncio.get_running_loop()
            _model = await loop.run_in_executor(None, _load_model)
    return _model


def _to_float32_array(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """faster-whisper 需要 float32 [-1, 1] @ 16kHz mono"""
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32) / 32768.0
    if sample_rate != 16000:
        # 简单线性重采样（音频质量已经够用，避免引入 scipy 依赖）
        ratio = 16000 / sample_rate
        new_len = int(len(samples) * ratio)
        idx = np.linspace(0, len(samples) - 1, new_len).astype(np.int64)
        samples = samples[idx]
    return samples


def transcribe_sync(samples: np.ndarray, sample_rate: int) -> Transcript | None:
    """同步转写（内部调用）"""
    audio = _to_float32_array(samples, sample_rate)
    duration = len(audio) / 16000

    if duration < 0.3:
        log.info("音频太短，跳过转写", duration=duration)
        return None

    # 同步获取模型（如果已经预热好就立即返回）
    global _model
    if _model is None:
        _model = _load_model()
    model = _model

    t0 = time.monotonic()
    segments, info = model.transcribe(  # type: ignore[attr-defined]
        audio,
        language=settings.stt.language or None,
        beam_size=settings.stt.beam_size,
        vad_filter=False,  # 我们前面已经做过 VAD
    )
    text_parts: list[str] = []
    logprobs: list[float] = []
    for seg in segments:
        text_parts.append(seg.text)
        if seg.avg_logprob is not None:
            logprobs.append(seg.avg_logprob)
    text = "".join(text_parts).strip()
    elapsed = time.monotonic() - t0
    avg_lp = sum(logprobs) / len(logprobs) if logprobs else None

    log.info(
        "转写完成",
        text=text,
        language=info.language,
        duration_sec=round(duration, 2),
        elapsed_sec=round(elapsed, 2),
        avg_logprob=round(avg_lp, 3) if avg_lp is not None else None,
    )
    return Transcript(
        text=text,
        language=info.language,
        duration_sec=duration,
        elapsed_sec=elapsed,
        avg_logprob=avg_lp,
    )


async def transcribe(samples: np.ndarray, sample_rate: int) -> Transcript | None:
    """异步转写"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: transcribe_sync(samples, sample_rate))


async def warm_up() -> None:
    """预热模型，避免首次调用延迟"""
    await get_model()
