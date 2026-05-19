"""麦克风录音 + VAD 自动断句 + 声音反馈

行为：
  1. 持续监听（不超时），直到 VAD 检测到语音开始
  2. 播放"叮"提示音 → 让用户知道"我听到了"
  3. 持续录音
  4. 静音超过 1.5 秒 → 播放"嘟"提示音 → 返回录音
  5. 超过 max_duration_sec → 强制返回
"""
from __future__ import annotations

import asyncio
import time
import winsound
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:
    webrtcvad = None  # type: ignore
    _HAS_VAD = False

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class AudioChunk:
    samples: np.ndarray  # int16 mono
    sample_rate: int
    duration_sec: float


def list_input_devices() -> list[dict]:
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_samplerate": dev["default_samplerate"],
                }
            )
    return devices


def _resolve_device() -> int | str | None:
    cfg = settings.audio.device
    if cfg is None:
        return None
    if cfg.isdigit():
        return int(cfg)
    for dev in list_input_devices():
        if cfg.lower() in dev["name"].lower():
            log.info("匹配输入设备", name=dev["name"], index=dev["index"])
            return dev["index"]
    log.warning("找不到匹配设备，回退默认", config=cfg)
    return None


def _make_vad():
    if not _HAS_VAD:
        log.warning("webrtcvad 未安装，VAD 功能降级为能量阈值")
        return None
    return webrtcvad.Vad(settings.vad.aggressiveness)


def _is_speech(vad, frame_bytes: bytes, sample_rate: int) -> bool:
    if vad is None:
        arr = np.frombuffer(frame_bytes, dtype=np.int16)
        rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
        return rms > 500.0
    return vad.is_speech(frame_bytes, sample_rate)


def _play_beep(kind: str = "start") -> None:
    """播放提示音（Windows 系统音）

    start: 叮~ 表示"我听到你了"
    end:   嘟~ 表示"收到，开始处理"
    """
    try:
        if kind == "start":
            winsound.Beep(800, 150)   # 800Hz 150ms — 短促高音"叮"
        elif kind == "end":
            winsound.Beep(500, 200)   # 500Hz 200ms — 低沉"嘟"
    except Exception:  # noqa: BLE001
        pass  # 无声卡时静默失败


def record_once(
    *,
    max_duration_sec: float = 30.0,
    on_dB=None,
) -> AudioChunk | None:
    """录一段话。持续监听直到检测到语音，然后录到静音为止。

    行为：
      1. 一直等（不超时），直到 VAD 检测到语音开始
      2. 播放"叮"提示音
      3. 持续录音
      4. 静音超过 silence_ms → 播放"嘟"提示音 → 返回
      5. 超过 max_duration_sec → 强制返回
    """
    sr = settings.audio.sample_rate
    block = settings.audio.block_size
    silence_ms = int(settings.vad.silence_threshold_seconds * 1000)

    vad = _make_vad()
    device = _resolve_device()

    log.info(
        "持续监听中（等待语音）",
        sample_rate=sr,
        block_size=block,
        silence_ms=silence_ms,
        max_duration=max_duration_sec,
    )

    frames: list[np.ndarray] = []
    speech_started = False
    last_speech_ts: float | None = None
    start: float | None = None

    try:
        with sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="int16",
            blocksize=block,
            device=device,
        ) as stream:
            while True:
                if start is not None and time.monotonic() - start > max_duration_sec:
                    log.warning("录音超过 max_duration，强制结束")
                    _play_beep("end")
                    break

                data, overflowed = stream.read(block)
                if overflowed:
                    log.debug("录音溢出")
                samples = data[:, 0] if data.ndim > 1 else data
                samples_i16 = samples.astype(np.int16)
                frame_bytes = samples_i16.tobytes()

                speaking = _is_speech(vad, frame_bytes, sr)

                if on_dB is not None:
                    rms = float(np.sqrt(np.mean(samples_i16.astype(np.float32) ** 2)))
                    db = 20.0 * np.log10(rms + 1e-6) - 60.0
                    on_dB(db, speaking)

                if speaking:
                    if not speech_started:
                        speech_started = True
                        start = time.monotonic()
                        log.info("检测到语音开始")
                        _play_beep("start")
                    last_speech_ts = time.monotonic()
                    frames.append(samples_i16.copy())
                elif speech_started:
                    frames.append(samples_i16.copy())
                    if last_speech_ts is not None:
                        silent_for_ms = (time.monotonic() - last_speech_ts) * 1000.0
                        if silent_for_ms >= silence_ms:
                            log.info("静音超时，结束录音", silent_ms=silent_for_ms)
                            _play_beep("end")
                            break
                # 还没开始说话 → 继续等（不超时）

    except sd.PortAudioError as e:
        log.error("音频设备错误", err=str(e))
        return None

    if not frames:
        log.info("未检测到语音")
        return None

    audio = np.concatenate(frames)
    duration = len(audio) / sr
    log.info("录音完成", duration_sec=round(duration, 2), samples=len(audio))
    return AudioChunk(samples=audio, sample_rate=sr, duration_sec=duration)


async def record_once_async(**kwargs) -> AudioChunk | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: record_once(**kwargs))


async def record_stream(*, block_ms: int = 30) -> AsyncGenerator[bytes, None]:
    """流式吐 int16 字节（给唤醒词检测用）"""
    sr = settings.audio.sample_rate
    block = int(sr * block_ms / 1000)
    device = _resolve_device()

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        if status:
            log.debug("流式状态", status=str(status))
        i16 = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        try:
            loop.call_soon_threadsafe(queue.put_nowait, i16)
        except asyncio.QueueFull:
            pass

    stream = sd.InputStream(
        samplerate=sr,
        channels=1,
        dtype="float32",
        blocksize=block,
        device=device,
        callback=callback,
    )
    stream.start()
    log.info("流式录音启动", sr=sr, block_ms=block_ms)

    try:
        while True:
            chunk = await queue.get()
            yield chunk
    finally:
        stream.stop()
        stream.close()
        log.info("流式录音停止")
