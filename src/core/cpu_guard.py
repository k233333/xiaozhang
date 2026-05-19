"""CPU/内存压力查询 + 高负载守护协程（v2.0 D11）

主动监控 CPU 占用，长时间高负载时建议切到 GAMING 模式（卸载本地模型让位给压制/编译/渲染）。
和 game_detector 的 cpu_load 检测分支互补：
  - game_detector 是单点采样（被动随 watchdog 查）
  - cpu_guard 是常驻协程，连续采样窗口判定，更快响应

触发逻辑：
  - 滑动窗口最近 N 秒，连续 K 次采样 > threshold → 强制切 GAMING
  - 之后 CPU 持续 < threshold * 0.6 持续 M 秒 → 自动切回 STANDARD

使用：
  await start_cpu_guard()           # 启动
  await stop_cpu_guard()            # 停止
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

import psutil

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


# ---------- 公开查询 API（保留旧用法）----------

def cpu_load_pct(interval: float = 0.0) -> float:
    return psutil.cpu_percent(interval=interval)


def memory_pressure() -> dict:
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / 1024**3, 2),
        "used_gb": round(vm.used / 1024**3, 2),
        "available_gb": round(vm.available / 1024**3, 2),
        "percent": vm.percent,
    }


def is_cpu_overloaded() -> bool:
    return cpu_load_pct(interval=0.1) > settings.resource_manager.thresholds.cpu_busy_percent


# ---------- 守护协程 ----------

@dataclass
class GuardState:
    samples: deque = field(default_factory=lambda: deque(maxlen=12))  # 最近 1 分钟的采样
    consecutive_high: int = 0
    consecutive_low: int = 0
    triggered_gaming: bool = False
    last_decision_ts: float = 0.0


_state = GuardState()
_task: asyncio.Task | None = None

# 滑动窗口配置（暂时硬编码，后续可移到 runtime.yaml）
SAMPLE_INTERVAL_SEC = 5.0
TRIGGER_HIGH_SAMPLES = 6     # 连续 6 次 > high → 触发降级（30 秒）
TRIGGER_LOW_SAMPLES = 12     # 连续 12 次 < low → 恢复（60 秒）
RECOVER_RATIO = 0.6          # CPU 跌到 threshold * 0.6 才算"恢复"


async def _guard_loop() -> None:
    from src.core.resource_manager import Mode, resource_manager  # noqa: PLC0415

    high_thresh = settings.resource_manager.thresholds.cpu_busy_percent
    low_thresh = high_thresh * RECOVER_RATIO

    log.info(
        "cpu_guard 启动",
        high=high_thresh,
        low=round(low_thresh, 1),
        sample_interval=SAMPLE_INTERVAL_SEC,
    )

    try:
        while True:
            cpu = psutil.cpu_percent(interval=1.0)  # 1 秒采样
            mp = memory_pressure()
            _state.samples.append((time.time(), cpu, mp["percent"]))

            # 用户强制模式优先：guard 暂停判断
            if settings.resource_manager.force_mode is not None:
                _state.consecutive_high = 0
                _state.consecutive_low = 0
                _state.triggered_gaming = False
                await asyncio.sleep(SAMPLE_INTERVAL_SEC - 1)
                continue

            if cpu > high_thresh:
                _state.consecutive_high += 1
                _state.consecutive_low = 0
                if (
                    _state.consecutive_high >= TRIGGER_HIGH_SAMPLES
                    and not _state.triggered_gaming
                    and resource_manager.mode != Mode.GAMING
                ):
                    log.warning(
                        "CPU 持续高负载，cpu_guard 主动切游戏模式（卸载本地模型）",
                        cpu_now=cpu,
                        sustained_samples=_state.consecutive_high,
                    )
                    resource_manager.load_for_mode(Mode.GAMING)
                    _state.triggered_gaming = True
                    _state.last_decision_ts = time.time()
            elif cpu < low_thresh:
                _state.consecutive_low += 1
                _state.consecutive_high = 0
                if (
                    _state.consecutive_low >= TRIGGER_LOW_SAMPLES
                    and _state.triggered_gaming
                    and resource_manager.mode == Mode.GAMING
                    # 但 game_detector 检测到真在玩游戏时不要回切
                ):
                    from src.core.game_detector import detector  # noqa: PLC0415
                    state = detector.check_once()
                    if not state.is_game:
                        log.info(
                            "CPU 已恢复正常 + 非游戏，cpu_guard 切回标准模式",
                            cpu_now=cpu,
                            sustained_samples=_state.consecutive_low,
                        )
                        resource_manager.load_for_mode(Mode.STANDARD)
                        _state.triggered_gaming = False
                        _state.last_decision_ts = time.time()
            else:
                # 中间地带，不计高也不计低
                _state.consecutive_high = max(0, _state.consecutive_high - 1)
                _state.consecutive_low = max(0, _state.consecutive_low - 1)

            await asyncio.sleep(SAMPLE_INTERVAL_SEC - 1)
    except asyncio.CancelledError:
        log.info("cpu_guard 退出")
        raise


async def start_cpu_guard() -> None:
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_guard_loop(), name="cpu_guard")


async def stop_cpu_guard() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    _task = None


def get_guard_state() -> dict:
    """供 status 命令查询"""
    return {
        "samples_count": len(_state.samples),
        "consecutive_high": _state.consecutive_high,
        "consecutive_low": _state.consecutive_low,
        "triggered_gaming": _state.triggered_gaming,
        "last_decision_ts": _state.last_decision_ts,
        "recent_cpu": [round(s[1], 1) for s in list(_state.samples)[-5:]],
    }
