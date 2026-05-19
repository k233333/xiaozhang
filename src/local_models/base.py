"""本地模型统一接口

DirectML / CPU 自动选择，提供 unload() 便于资源管理器一键卸载所有本地模型。
所有具体模型（wake_word / vad / sensevoice / omniparser）继承本类。
"""
from __future__ import annotations

import gc
from typing import Any

from src.core.config import LocalModelCfg, settings
from src.core.logger import get_logger

log = get_logger(__name__)


def available_providers() -> list[str]:
    try:
        import onnxruntime as ort  # noqa: PLC0415
        return list(ort.get_available_providers())
    except ImportError:
        log.warning("onnxruntime 未安装")
        return []


def has_directml() -> bool:
    return "DmlExecutionProvider" in available_providers()


class LocalModel:
    """统一本地模型基类

    子类应实现：
      - _load() 加载实际模型
      - infer/predict 推理接口
    """

    name: str = "base"

    def __init__(self, cfg: LocalModelCfg) -> None:
        self.cfg = cfg
        self.model_path = settings.resolve_path(cfg.model_path)
        self.providers = self._resolve_providers()
        self._loaded = False
        self._session: Any = None

    def _resolve_providers(self) -> list[str]:
        avail = available_providers()
        chain: list[str] = []
        if self.cfg.backend == "directml" and "DmlExecutionProvider" in avail:
            chain.append("DmlExecutionProvider")
        if "CPUExecutionProvider" in avail:
            chain.append("CPUExecutionProvider")
        return chain

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> bool:
        if self._loaded:
            return True
        if not self.model_path.exists():
            log.warning(
                "模型文件不存在，跳过加载",
                name=self.name,
                path=str(self.model_path),
            )
            return False
        try:
            self._load()
            self._loaded = True
            log.info(
                "本地模型已加载",
                name=self.name,
                providers=self.providers,
                path=str(self.model_path),
            )
            return True
        except Exception as e:  # noqa: BLE001
            log.exception("本地模型加载失败", name=self.name, err=str(e))
            return False

    def unload(self) -> None:
        if not self._loaded:
            return
        try:
            self._unload()
        except Exception as e:  # noqa: BLE001
            log.warning("卸载本地模型异常", name=self.name, err=str(e))
        self._session = None
        self._loaded = False
        gc.collect()
        log.info("本地模型已卸载", name=self.name)

    def _load(self) -> None:
        """默认：用 onnxruntime 加载"""
        import onnxruntime as ort  # noqa: PLC0415
        self._session = ort.InferenceSession(
            str(self.model_path),
            providers=self.providers,
        )

    def _unload(self) -> None:
        del self._session
