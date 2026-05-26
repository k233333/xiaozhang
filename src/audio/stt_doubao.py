# coding: utf-8
"""豆包输入法 ASR — 最高中文识别准确率

调用豆包输入法云端 ASR API（逆向协议，无需安装豆包输入法）。
首次运行自动注册虚拟设备，凭据缓存到 data/doubao_credentials.json。

优势：
- 字节跳动中文 ASR，口语识别极强（"重启"不会识别成"冲起"）
- 延迟 ~0.5-1s（云端流式）
- 免费（豆包输入法服务）
- 无需本地 GPU

降级策略：
- 豆包 ASR 失败 → 自动回退 SenseVoice GPU → faster-whisper CPU
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import numpy as np

from src.core.logger import get_logger

log = get_logger(__name__)

_CREDENTIAL_PATH = Path("data/doubao_credentials.json")
_config = None
_available: bool | None = None  # None=未检测, True=可用, False=不可用


def _get_config():
    global _config
    if _config is not None:
        return _config
    try:
        # 预加载 opus.dll（opuslib 在 Windows 上找不到时的兜底）
        _preload_opus()

        from doubaoime_asr import ASRConfig  # noqa: PLC0415
        _CREDENTIAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        _config = ASRConfig(
            credential_path=str(_CREDENTIAL_PATH),
            sample_rate=16000,
            channels=1,
            enable_punctuation=True,
        )
        return _config
    except ImportError:
        log.warning("doubaoime_asr 未安装")
        return None
    except Exception as e:
        log.warning("豆包 ASR 配置失败", err=str(e))
        return None


def _preload_opus() -> None:
    """在 Windows 上预加载 opus.dll，让 opuslib 能找到它"""
    import sys
    if sys.platform != "win32":
        return
    import ctypes
    import os

    # 候选路径
    candidates = [
        # venv Scripts 目录（我们复制过去的）
        str(Path(sys.executable).parent / "opus.dll"),
        # pyogg 包目录
    ]
    try:
        import pyogg  # noqa: PLC0415
        candidates.append(str(Path(pyogg.__file__).parent / "opus.dll"))
    except ImportError:
        pass

    for path in candidates:
        if os.path.exists(path):
            try:
                ctypes.cdll.LoadLibrary(path)
                log.info("opus.dll 预加载成功", path=path)
                return
            except Exception as e:
                log.debug("opus.dll 预加载失败", path=path, err=str(e))

    log.debug("未找到 opus.dll，opuslib 将自行查找")


async def transcribe(samples: np.ndarray, sample_rate: int) -> str:
    """用豆包 ASR 转写音频。

    Args:
        samples: int16 PCM 音频数据
        sample_rate: 采样率（会自动重采样到 16000）

    Returns:
        识别文字，失败返回空字符串
    """
    global _available

    if _available is False:
        return ""

    config = _get_config()
    if config is None:
        _available = False
        return ""

    # 重采样到 16000Hz
    if sample_rate != 16000:
        ratio = 16000 / sample_rate
        new_len = int(len(samples) * ratio)
        idx = np.linspace(0, len(samples) - 1, new_len).astype(np.int64)
        samples = samples[idx]

    # 确保 int16
    if samples.dtype != np.int16:
        samples = (samples * 32768).clip(-32768, 32767).astype(np.int16)

    pcm_bytes = samples.tobytes()

    t0 = time.monotonic()
    try:
        from doubaoime_asr import transcribe as _transcribe  # noqa: PLC0415

        text = await _transcribe(pcm_bytes, config=config)
        text = (text or "").strip()
        elapsed = time.monotonic() - t0
        log.info("豆包 ASR 转写完成", text=text[:60], elapsed_sec=round(elapsed, 2))
        _available = True
        return text

    except Exception as e:
        elapsed = time.monotonic() - t0
        log.warning("豆包 ASR 失败，将回退", err=str(e), elapsed_sec=round(elapsed, 2))
        # 首次失败不标记为不可用，可能是网络抖动
        return ""


async def is_available() -> bool:
    """检查豆包 ASR 是否可用（发一个测试请求）"""
    global _available
    if _available is not None:
        return _available

    config = _get_config()
    if config is None:
        _available = False
        return False

    # 用 1 秒静音测试连通性
    silence = np.zeros(16000, dtype=np.int16)
    try:
        await transcribe(silence, 16000)
        # 静音识别结果为空是正常的，只要不抛异常就算通
        _available = True
        log.info("豆包 ASR 连通性测试通过")
        return True
    except Exception as e:
        log.warning("豆包 ASR 不可用", err=str(e))
        _available = False
        return False
