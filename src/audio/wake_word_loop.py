# coding: utf-8
"""唤醒词持续监听循环（方案 C：VAD 门控 + 自训练分类器）

流程：
  1. 持续录音（2 秒片段）
  2. 先用能量阈值粗筛（无声直接丢弃，CPU 0%）
  3. 有声音 → 跑自训练 ONNX 分类器（< 1ms）
  4. 概率 > threshold → 判定为"小张" → 播放"叮" → 回调通知上层

资源占用：
  - 无声时：CPU < 0.5%（只做能量计算）
  - 有声时：CPU < 1%（mel 特征 + ONNX 推理 < 1ms）
  - 内存：+26KB（模型）
"""
from __future__ import annotations

import asyncio
import time

import numpy as np
import sounddevice as sd
import winsound

from src.audio.wake_word_custom import detect, get_threshold, is_loaded, _load
from src.core.config import settings
from src.core.logger import get_logger
from src.core.state_machine import State, StateMachine

log = get_logger(__name__)

# 能量阈值：低于此值直接丢弃（环境底噪通常 RMS < 200）
ENERGY_THRESHOLD = 300
# 连续检测到唤醒词的最小次数（防止单次误触发）
MIN_CONSECUTIVE = 1
# 两次唤醒之间的冷却时间（秒）
COOLDOWN_SEC = 3.0

# 唤醒后立刻录的指令音频（秒）
POST_WAKE_RECORD_SEC = 6.0


class WakeWordLoop:
    """唤醒词持续监听协程"""

    def __init__(self, sm: StateMachine) -> None:
        self.sm = sm
        self._last_trigger_ts: float = 0.0
        self._silent_chunks: int = 0
        # 唤醒后录到的指令音频，供 main.py 取走
        self._pending_audio: np.ndarray | None = None
        self._pending_sr: int = 16000

    def take_pending_audio(self) -> tuple[np.ndarray, int] | None:
        """取走唤醒后录到的指令音频（只能取一次）"""
        if self._pending_audio is not None:
            audio = self._pending_audio
            sr = self._pending_sr
            self._pending_audio = None
            return audio, sr
        return None

    async def run(self) -> None:
        """主循环：持续录 2 秒片段 → 检测唤醒词"""
        if not is_loaded():
            if not _load():
                log.error("唤醒词模型加载失败，监听不启动")
                return

        sr = settings.audio.sample_rate
        chunk_duration = 2.0  # 每次录 2 秒
        chunk_samples = int(sr * chunk_duration)
        threshold = get_threshold()
        device = self._resolve_device()

        log.info(
            "唤醒词监听启动",
            threshold=threshold,
            energy_threshold=ENERGY_THRESHOLD,
            chunk_sec=chunk_duration,
        )

        loop = asyncio.get_running_loop()

        while True:
            # 录 2 秒
            try:
                audio = await loop.run_in_executor(
                    None,
                    lambda: self._record_chunk(chunk_samples, sr, device),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("录音失败", err=str(e))
                await asyncio.sleep(1)
                continue

            if audio is None:
                continue

            # 能量粗筛
            rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
            if rms < ENERGY_THRESHOLD:
                # 纯静音，跳过（CPU 0%）
                # 每 30 个静音块输出一次 RMS，确认麦克风在工作
                self._silent_chunks += 1
                if self._silent_chunks % 30 == 0:
                    log.info("静音块统计", silent_chunks=self._silent_chunks, last_rms=round(rms, 1), threshold=ENERGY_THRESHOLD)
                continue

            # 有声音，跑分类器
            log.info("能量触发", rms=round(rms, 1), threshold=ENERGY_THRESHOLD)
            prob = detect(audio, sr)
            log.info("分类器结果", prob=round(prob, 4), wake_threshold=threshold)
            if prob >= threshold:
                # 冷却检查
                now = time.time()
                if now - self._last_trigger_ts < COOLDOWN_SEC:
                    continue
                self._last_trigger_ts = now

                log.info("唤醒词命中！", prob=round(prob, 4), threshold=threshold)
                self._play_ding()

                # 唤醒后立刻录指令（不等 VAD，直接录 POST_WAKE_RECORD_SEC 秒）
                # 这样用户说完唤醒词后紧接着说指令，不会卡死
                if self.sm.state == State.IDLE:
                    await self.sm.transition(State.LISTENING)
                    post_samples = int(sr * POST_WAKE_RECORD_SEC)
                    try:
                        cmd_audio = await loop.run_in_executor(
                            None,
                            lambda: self._record_chunk(post_samples, sr, device),
                        )
                        if cmd_audio is not None and len(cmd_audio) > 0:
                            self._pending_audio = cmd_audio
                            self._pending_sr = sr
                            log.info("唤醒后指令录音完成", duration_sec=round(len(cmd_audio)/sr, 2))
                    except Exception as e:  # noqa: BLE001
                        log.warning("唤醒后录音失败", err=str(e))

    def _record_chunk(self, samples: int, sr: int, device) -> np.ndarray | None:
        """同步录一个 chunk"""
        try:
            audio = sd.rec(samples, samplerate=sr, channels=1, dtype="int16", device=device, blocking=True)
            return audio.flatten()
        except sd.PortAudioError as e:
            log.warning("音频设备错误", err=str(e))
            return None

    def _resolve_device(self):
        cfg = settings.audio.device
        if cfg is None:
            return None
        if cfg.isdigit():
            return int(cfg)
        from src.audio.recorder import list_input_devices
        for dev in list_input_devices():
            if cfg.lower() in dev["name"].lower():
                return dev["index"]
        return None

    def _play_ding(self):
        """播放"叮"提示音"""
        try:
            winsound.Beep(800, 150)
        except Exception:
            pass
