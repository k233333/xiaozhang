"""CPU/内存压力查询 + 高负载保护建议

实际的"切到 GAMING 模式"逻辑由 game_detector 的 cpu_load 检测分支负责。
本模块只提供数据查询 API。
"""
from __future__ import annotations

import psutil

from src.core.config import settings


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
