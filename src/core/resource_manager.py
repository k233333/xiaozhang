"""资源管理器（v2.0 核心）

watchdog 协程定期查 game_detector，根据结果在 STANDARD / GAMING 之间切换。
切换前 switch_delay 秒抖动抑制。
切到 GAMING：unload sensevoice / silero_vad / omniparser
切回 STANDARD：load 上述模型
"""
from __future__ import annotations

import asyncio
import threading
import time
from enum import Enum

from src.core.config import settings
from src.core.logger import get_logger
from src.local_models.base import LocalModel
from src.local_models.omniparser_model import OmniParserModel
from src.local_models.rapidocr_model import RapidOCRModel
from src.local_models.sensevoice_model import SenseVoiceModel
from src.local_models.vad_model import SileroVadModel
from src.local_models.wake_word_model import WakeWordModel

log = get_logger(__name__)


class Mode(str, Enum):
    STANDARD = "standard"
    GAMING = "gaming"


_MODEL_CLASSES = {
    "wake_word": WakeWordModel,
    "silero_vad": SileroVadModel,
    "sensevoice": SenseVoiceModel,
    "omniparser": OmniParserModel,
    "rapidocr": RapidOCRModel,
}


class ResourceManager:
    def __init__(self) -> None:
        self._models: dict[str, LocalModel] = {}
        self._mode: Mode = Mode.STANDARD
        self._lock = threading.Lock()
        self._watchdog_task: asyncio.Task | None = None
        self._listeners: list = []
        self._pending_switch_to: Mode | None = None
        self._pending_switch_at: float = 0.0
        self._instantiate_all()

    @property
    def mode(self) -> Mode:
        return self._mode

    def add_mode_listener(self, fn) -> None:
        self._listeners.append(fn)

    def get_model(self, name: str) -> LocalModel | None:
        m = self._models.get(name)
        if m is None or not m.is_loaded():
            return None
        return m

    def load_for_mode(self, mode: Mode) -> None:
        target_names = set(settings.mode_models.get(mode.value, []))
        log.info("按模式加载模型", mode=mode.value, targets=sorted(target_names))
        with self._lock:
            for name, m in self._models.items():
                if name in target_names:
                    if not m.is_loaded():
                        m.load()
                else:
                    if m.is_loaded():
                        m.unload()
            self._mode = mode
        self._notify_listeners(mode)

    def force_mode(self, mode: Mode | None) -> None:
        settings.resource_manager.force_mode = mode.value if mode else None
        if mode is not None:
            self.load_for_mode(mode)

    async def start_watchdog(self) -> None:
        if self._watchdog_task is not None:
            return
        # 启动时只加载轻量模型（wake_word + silero_vad），1.5s 即可响应唤醒词
        immediate = settings.mode_models.get("standard_immediate", [])
        if immediate:
            log.info("启动：立即加载轻量模型", targets=immediate)
            self._load_subset(immediate)
        else:
            self.load_for_mode(self._mode)

        self._watchdog_task = asyncio.create_task(
            self._watchdog_loop(), name="rm_watchdog"
        )
        # 60 秒后加载重模型（sensevoice + omniparser）
        self._deferred_task = asyncio.create_task(
            self._deferred_load(), name="rm_deferred"
        )
        log.info("ResourceManager watchdog 启动")

    async def stop_watchdog(self) -> None:
        if self._watchdog_task is None:
            return
        self._watchdog_task.cancel()
        self._watchdog_task = None
        if hasattr(self, "_deferred_task") and self._deferred_task is not None:
            self._deferred_task.cancel()
            self._deferred_task = None
        log.info("ResourceManager watchdog 停止")

    def _load_subset(self, names: list[str]) -> None:
        """只加载指定名称的模型（不卸载其他）"""
        with self._lock:
            for name in names:
                m = self._models.get(name)
                if m is not None and not m.is_loaded():
                    m.load()

    async def _deferred_load(self) -> None:
        """启动 60 秒后加载重模型（sensevoice + omniparser）"""
        delay = 60
        log.info("延迟加载计划", delay_sec=delay, targets=settings.mode_models.get("standard_deferred", []))
        try:
            await asyncio.sleep(delay)
            # 如果已经切到游戏模式就不加载了
            if self._mode != Mode.STANDARD:
                log.info("延迟加载取消（已切到游戏模式）")
                return
            deferred = settings.mode_models.get("standard_deferred", [])
            if deferred:
                log.info("延迟加载开始", targets=deferred)
                self._load_subset(deferred)
                log.info("延迟加载完成")
        except asyncio.CancelledError:
            log.info("延迟加载被取消")
            raise

    def _instantiate_all(self) -> None:
        for name, mc in _MODEL_CLASSES.items():
            cfg = settings.local_models.get(name)
            if cfg is None:
                log.debug("local_models 未配置该项", name=name)
                continue
            try:
                self._models[name] = mc(cfg)
            except Exception as e:  # noqa: BLE001
                log.warning("实例化本地模型失败", name=name, err=str(e))

    def _notify_listeners(self, new_mode: Mode) -> None:
        for fn in self._listeners:
            try:
                fn(new_mode)
            except Exception as e:  # noqa: BLE001
                log.exception("listener 异常", err=str(e))

    async def _watchdog_loop(self) -> None:
        from src.core.game_detector import detector  # noqa: PLC0415

        try:
            while True:
                try:
                    state = detector.check_once()
                    target = Mode.GAMING if state.is_game else Mode.STANDARD
                    if target != self._mode:
                        now = time.time()
                        if (
                            self._pending_switch_to != target
                            or self._pending_switch_at == 0.0
                        ):
                            self._pending_switch_to = target
                            self._pending_switch_at = now
                            log.info(
                                "检测到模式变化，进入抑制窗口",
                                from_=self._mode.value,
                                to=target.value,
                                method=state.matched_method,
                                delay_sec=settings.resource_manager.switch_delay,
                            )
                        elif (
                            now - self._pending_switch_at
                            >= settings.resource_manager.switch_delay
                        ):
                            old = self._mode
                            self.load_for_mode(target)
                            log.info(
                                "模式切换完成",
                                from_=old.value,
                                to=target.value,
                                method=state.matched_method,
                                fg=state.fg_process,
                            )
                            self._pending_switch_to = None
                            self._pending_switch_at = 0.0
                    else:
                        if self._pending_switch_to is not None:
                            self._pending_switch_to = None
                            self._pending_switch_at = 0.0
                except Exception as e:  # noqa: BLE001
                    log.exception("watchdog 异常", err=str(e))
                await asyncio.sleep(settings.resource_manager.watchdog_interval)
        except asyncio.CancelledError:
            log.info("watchdog 退出")
            raise


resource_manager = ResourceManager()
