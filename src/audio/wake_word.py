"""两段式唤醒词检测

D10-11 阶段才会真正启用。当前实现一个最小可用骨架：
  1. 用 openWakeWord 自带的英文模型（默认）做粗筛
  2. 检测到唤醒 → 进入 ARMED → 4 秒窗口
  3. 二次确认（再听到 primary/secondary）→ 进入 LISTENING

由于"小张"是中文，需要用户自训练模型放在 wake_word.model_dir。
当前若模型目录为空，print 警告并禁用。
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import numpy as np

from src.core.config import settings
from src.core.logger import get_logger
from src.core.state_machine import State, StateMachine

log = get_logger(__name__)


class WakeWordDetector:
    def __init__(self, sm: StateMachine) -> None:
        self.sm = sm
        self._oww: object | None = None
        self._enabled = settings.wake_word.enabled

    def _load(self) -> bool:
        if self._oww is not None:
            return True
        try:
            import openwakeword  # noqa: PLC0415
            from openwakeword.model import Model  # noqa: PLC0415

            model_dir = settings.resolve_path(settings.wake_word.model_dir)
            model_dir.mkdir(parents=True, exist_ok=True)
            custom_models = list(model_dir.glob("*.onnx")) + list(model_dir.glob("*.tflite"))

            if custom_models:
                log.info("加载自训练唤醒词模型", count=len(custom_models))
                self._oww = Model(
                    wakeword_models=[str(p) for p in custom_models],
                    inference_framework="onnx",
                )
            else:
                log.warning(
                    "未找到自训练唤醒词模型，使用 openWakeWord 默认（仅英文支持）",
                    model_dir=str(model_dir),
                )
                self._oww = Model(inference_framework="onnx")
            _ = openwakeword  # 留一行避免未使用警告
            return True
        except Exception as e:
            log.error("openWakeWord 加载失败", err=str(e))
            self._enabled = False
            return False

    async def run(self) -> None:
        """常驻协程：监听音频流，触发唤醒后切换状态"""
        if not self._enabled:
            log.warning("唤醒词检测未启用（config.wake_word.enabled=False）")
            return
        if not self._load():
            return

        from src.audio.recorder import record_stream  # noqa: PLC0415

        threshold = settings.wake_word.primary_threshold
        armed_window = settings.wake_word.armed_window_seconds

        log.info("唤醒词检测启动", primary=settings.wake_word.primary, threshold=threshold)

        async for chunk in record_stream(block_ms=80):
            audio = np.frombuffer(chunk, dtype=np.int16)
            scores = self._oww.predict(audio)  # type: ignore[union-attr]

            # 任一模型超过阈值就触发
            triggered = any(s > threshold for s in scores.values())
            if not triggered:
                continue

            log.info("第一段唤醒命中", scores=scores)
            await self.sm.transition(State.ARMED)
            confirmed = await self._wait_second_stage(armed_window)
            if confirmed:
                await self.sm.transition(State.LISTENING)
            else:
                await self.sm.transition(State.IDLE)

    async def _wait_second_stage(self, window_sec: float) -> bool:
        """ARMED 状态下等待第二段确认。

        最简实现：调用 record_once 录一小段，转写后看是否含 primary/secondary 关键词。
        D10-11 再优化为流式。
        """
        from src.audio.recorder import record_once_async  # noqa: PLC0415
        from src.audio.stt import transcribe  # noqa: PLC0415

        log.info("进入 ARMED，等待二次确认", window_sec=window_sec)
        deadline = time.monotonic() + window_sec
        while time.monotonic() < deadline:
            chunk = await record_once_async(max_duration_sec=window_sec)
            if chunk is None:
                continue
            tr = await transcribe(chunk.samples, chunk.sample_rate)
            if tr is None or not tr.text:
                continue
            text = tr.text
            if settings.wake_word.cancel_word in text:
                log.info("用户取消唤醒")
                return False
            if (
                settings.wake_word.secondary in text
                or settings.wake_word.primary in text
            ):
                log.info("第二段唤醒确认", text=text)
                return True
        log.info("ARMED 超时，回到 IDLE")
        return False
