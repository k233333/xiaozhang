"""麦克风录音 + VAD 自动断句

用 sounddevice 持续读流，webrtcvad 判定语音活动。
检测到说话开始 → 累积音频；检测到静音超过 silence_timeout_ms → 输出整段并返回。

提供两种用法：
  1. record_once()  - 同步阻塞，返回一段完整音频
  2. record_stream() - 异步生成器，持续吐音频块（给唤醒词检测用）
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:  # webrtcvad 装载失败时降级为定时录音
    webrtcvad = None  # type: ignore
    _HAS_VAD = False

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class AudioChunk:
    """一段录音"""

    samples: np.ndarray  # int16 mono
    sample_rate: int
    duration_sec: float


def list_input_devices() -> list[dict]:
    """列出所有可用输入设备"""
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
    """根据 config.audio.device 解析为 sounddevice 接受的标识"""
    cfg = settings.audio.device
    if cfg is None:
        return None
    # 如果是数字字符串，转 int
    if cfg.isdigit():
        return int(cfg)
    # 否则模糊匹配设备名
    for dev in list_input_devices():
        if cfg.lower() in dev["name"].lower():
            log.info("匹配到输入设备", config=cfg, device=dev["name"], index=dev["index"])
            return dev["index"]
    log.warning("找不到匹配设备，回退默认", config=cfg)
    return None


def _make_vad() -> object | None:
    if not _HAS_VAD:
        log.warning("webrtcvad 未安装，VAD 功能降级")
        return None
    return webrtcvad.Vad(settings.audio.vad_aggressiveness)


def _is_speech(vad: object | None, frame_bytes: bytes, sample_rate: int) -> bool:
    if vad is None:
        # 降级：能量阈值
        arr = np.frombuffer(frame_bytes, dtype=np.int16)
        rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
        return rms > 500.0
    return vad.is_speech(frame_bytes, sample_rate)  # type: ignore[union-attr]


def record_once(
    *,
    max_duration_sec: float = 30.0,
    on_dB: callable = None,  # type: ignore[type-arg]
) -> AudioChunk | None:
    """同步录一段话。检测到静音超过 silence_timeout_ms 则返回。

    on_dB: 可选回调，每帧调用一次给 dB 电平（供终端可视化）。
    超过 max_duration_sec 强制返回。
    """
    sr = settings.audio.sample_rate
    block = settings.audio.block_size  # 30ms 一帧
    silence_ms = settings.audio.silence_timeout_ms

    vad = _make_vad()
    device = _resolve_device()

    log.info(
        "开始录音",
        sample_rate=sr,
        block_size=block,
        silence_ms=silence_ms,
        max_duration=max_duration_sec,
    )

    frames: list[np.ndarray] = []
    speech_started = False
    last_speech_ts: float | None = None
    start = time.monotonic()

    try:
        with sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="int16",
            blocksize=block,
            device=device,
        ) as stream:
            while True:
                if time.monotonic() - start > max_duration_sec:
                    log.warning("录音超过 max_duration，强制结束")
                    break
                data, overflowed = stream.read(block)
                if overflowed:
                    log.debug("录音溢出（设备速度跟不上）")
                samples = data[:, 0] if data.ndim > 1 else data  # mono
                samples_i16 = samples.astype(np.int16)
                frame_bytes = samples_i16.tobytes()

                speaking = _is_speech(vad, frame_bytes, sr)

                # dB 回调
                if on_dB is not None:
                    rms = float(np.sqrt(np.mean(samples_i16.astype(np.float32) ** 2)))
                    db = 20.0 * np.log10(rms + 1e-6) - 60.0  # 粗略归一
                    on_dB(db, speaking)

                if speaking:
                    if not speech_started:
                        speech_started = True
                        log.debug("检测到语音开始")
                    last_speech_ts = time.monotonic()
                    frames.append(samples_i16.copy())
                elif speech_started:
                    # 已经开始说话，累积静音帧（保留一段静音让结尾不被切掉）
                    frames.append(samples_i16.copy())
                    if last_speech_ts is not None:
                        silent_for_ms = (time.monotonic() - last_speech_ts) * 1000.0
                        if silent_for_ms >= silence_ms:
                            log.info("检测到静音超时，结束录音", silent_ms=silent_for_ms)
                            break
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
    """异步包装"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: record_once(**kwargs))


async def record_stream(
    *,
    block_ms: int = 30,
) -> AsyncGenerator[bytes, None]:
    """异步流式吐音频帧（int16 bytes），给唤醒词检测用。

    每个 yield 是 block_ms 毫秒的原始字节。
    """
    sr = settings.audio.sample_rate
    block = int(sr * block_ms / 1000)
    device = _resolve_device()

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        if status:
            log.debug("流式录音状态", status=str(status))
        # indata 是 numpy float32 [-1,1]，转 int16
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
    log.info("流式录音启动", sample_rate=sr, block_ms=block_ms)

    try:
        while True:
            chunk = await queue.get()
            yield chunk
    finally:
        stream.stop()
        stream.close()
        log.info("流式录音停止")
