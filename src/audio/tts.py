# coding: utf-8
"""TTS 语音合成模块 — 基于 edge-tts（微软免费 TTS）

特性：
- 异步非阻塞：不卡主线程
- 中文女声（晓晓）音质好、延迟低
- 自动缓存：相同文字不重复合成
- 播放用 sounddevice（项目已有依赖）
- 静默失败：TTS 挂了不影响主流程

用法：
    from src.audio.tts import speak, speak_sync
    await speak("好的，正在打开抖音")     # 异步
    speak_sync("已完成")                  # 同步（阻塞）
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import tempfile
import threading
from pathlib import Path

from src.core.logger import get_logger

log = get_logger(__name__)

# 缓存目录
_CACHE_DIR = Path(tempfile.gettempdir()) / "xiaozhang_tts_cache"
_CACHE_DIR.mkdir(exist_ok=True)

# 默认语音：晓晓（中文女声，自然流畅）
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

# 最大缓存文件数（防止磁盘爆满）
_MAX_CACHE_FILES = 200

# 是否正在播放（防止重叠）
_playing_lock = threading.Lock()
_is_playing = False


def _get_cache_path(text: str, voice: str) -> Path:
    """根据文字+语音生成缓存文件路径"""
    key = hashlib.md5(f"{voice}:{text}".encode()).hexdigest()[:12]
    return _CACHE_DIR / f"{key}.mp3"


def _cleanup_cache() -> None:
    """缓存文件超限时删除最旧的"""
    try:
        files = sorted(_CACHE_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
        if len(files) > _MAX_CACHE_FILES:
            for f in files[: len(files) - _MAX_CACHE_FILES]:
                f.unlink(missing_ok=True)
    except Exception:
        pass


async def _synthesize(text: str, voice: str = DEFAULT_VOICE) -> Path | None:
    """调用 edge-tts 合成语音，返回 mp3 文件路径（有缓存）"""
    cache_path = _get_cache_path(text, voice)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(cache_path))

        if cache_path.exists() and cache_path.stat().st_size > 0:
            _cleanup_cache()
            return cache_path
        else:
            return None
    except Exception as e:
        log.warning("TTS 合成失败", err=str(e), text=text[:30])
        return None


def _play_audio_file(filepath: Path) -> None:
    """用 sounddevice 播放 mp3/wav 文件（阻塞）"""
    global _is_playing
    try:
        import sounddevice as sd
        import soundfile as sf

        # edge-tts 输出 mp3，soundfile 需要通过 ffmpeg 或转 wav
        # 优先用 pydub 解码 mp3（如果有），否则用 winsound 播放
        try:
            # 尝试直接用 soundfile 读（需要 libsndfile 支持 mp3）
            data, samplerate = sf.read(str(filepath))
            with _playing_lock:
                _is_playing = True
            sd.play(data, samplerate)
            sd.wait()
        except Exception:
            # soundfile 不支持 mp3 → 用 Windows 自带的 Media Foundation 播放
            _play_with_winmm(filepath)
    except Exception as e:
        log.warning("TTS 播放失败", err=str(e))
    finally:
        with _playing_lock:
            _is_playing = False


def _play_with_winmm(filepath: Path) -> None:
    """用 Windows MCI 接口播放 mp3（兜底方案，Windows 原生支持）"""
    import ctypes
    import time

    winmm = ctypes.windll.winmm

    # MCI 命令播放 mp3
    cmd_open = f'open "{filepath}" type mpegvideo alias tts_audio'
    cmd_play = "play tts_audio wait"
    cmd_close = "close tts_audio"

    buf = ctypes.create_unicode_buffer(256)

    err = winmm.mciSendStringW(cmd_open, buf, 256, 0)
    if err != 0:
        log.debug("MCI open 失败", err=err)
        return

    try:
        with _playing_lock:
            global _is_playing
            _is_playing = True
        winmm.mciSendStringW(cmd_play, buf, 256, 0)
    finally:
        winmm.mciSendStringW(cmd_close, buf, 256, 0)
        with _playing_lock:
            _is_playing = False


async def speak(text: str, voice: str = DEFAULT_VOICE) -> bool:
    """异步合成并播放语音（非阻塞主循环）

    Args:
        text: 要播报的文字
        voice: edge-tts 语音名称

    Returns:
        是否成功播放
    """
    if not text or not text.strip():
        return False

    # 截断过长文本（TTS 太长会很慢）
    text = text.strip()
    if len(text) > 200:
        text = text[:200]

    filepath = await _synthesize(text, voice)
    if filepath is None:
        return False

    # 在线程池中播放，不阻塞 asyncio 事件循环
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _play_audio_file, filepath)
    return True


def speak_sync(text: str, voice: str = DEFAULT_VOICE) -> bool:
    """同步版本（阻塞当前线程直到播放完毕）

    适用于非 async 上下文（如 xz.py CLI）。
    """
    if not text or not text.strip():
        return False

    text = text.strip()
    if len(text) > 200:
        text = text[:200]

    try:
        loop = asyncio.new_event_loop()
        filepath = loop.run_until_complete(_synthesize(text, voice))
        loop.close()
    except Exception as e:
        log.warning("TTS 同步合成失败", err=str(e))
        return False

    if filepath is None:
        return False

    _play_audio_file(filepath)
    return True


def is_playing() -> bool:
    """当前是否正在播放 TTS"""
    with _playing_lock:
        return _is_playing
