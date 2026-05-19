# coding: utf-8
"""自训练唤醒词检测器（基于 mel 特征 + ONNX 分类器）

模型：models/wake_word/xiaozhang_wakeword.onnx（26KB，99.8% 准确率）
输入：2 秒 16kHz int16 音频 → 80 维 mel 特征 → ONNX 推理 → 概率
阈值：> 0.7 判定为"小张"

资源占用：CPU < 0.5%（每 2 秒推理一次，推理本身 < 1ms）
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

_session: ort.InferenceSession | None = None
_config: dict | None = None


def _load():
    global _session, _config
    model_path = settings.resolve_path("models/wake_word/xiaozhang_wakeword.onnx")
    config_path = settings.resolve_path("models/wake_word/xiaozhang_wakeword_config.json")

    if not model_path.exists():
        log.warning("唤醒词模型不存在", path=str(model_path))
        return False
    if not config_path.exists():
        log.warning("唤醒词配置不存在", path=str(config_path))
        return False

    _config = json.loads(config_path.read_text(encoding="utf-8"))
    _session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    log.info(
        "唤醒词模型加载完成",
        accuracy=_config.get("cv_accuracy"),
        threshold=_config.get("threshold"),
        feature_dim=_config.get("feature_dim"),
    )
    return True


def is_loaded() -> bool:
    return _session is not None


def compute_mel_features(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """从 2 秒音频提取 80 维 mel 特征（mean + std of 40 mel bins）"""
    n_mels = 40
    n_fft = 512
    hop = 160

    # 分帧
    n_frames = (len(audio) - n_fft) // hop + 1
    if n_frames <= 0:
        return np.zeros(n_mels * 2, dtype=np.float32)

    frames = np.zeros((n_frames, n_fft))
    for i in range(n_frames):
        frames[i] = audio[i * hop:i * hop + n_fft]

    # 加窗 + FFT
    window = np.hanning(n_fft)
    frames *= window
    spectrum = np.abs(np.fft.rfft(frames, n=n_fft))
    power = spectrum ** 2

    # Mel 滤波器组
    fmin, fmax = 0, sr / 2
    mel_min = 2595 * np.log10(1 + fmin / 700)
    mel_max = 2595 * np.log10(1 + fmax / 700)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filterbank = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(n_mels):
        left = bin_points[i]
        center = bin_points[i + 1]
        right = bin_points[i + 2]
        for j in range(left, center):
            if center > left:
                filterbank[i, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right > center:
                filterbank[i, j] = (right - j) / (right - center)

    mel_spec = np.dot(power, filterbank.T)
    mel_spec = np.log(mel_spec + 1e-8)

    # 统计特征
    features = np.concatenate([mel_spec.mean(axis=0), mel_spec.std(axis=0)])
    return features.astype(np.float32)


def detect(audio_int16: np.ndarray, sample_rate: int = 16000) -> float:
    """检测音频中是否包含"小张"

    返回概率 [0, 1]。> threshold 判定为唤醒。
    """
    global _session, _config
    if _session is None:
        if not _load():
            return 0.0

    # 转 float32
    audio = audio_int16.astype(np.float32) / 32768.0

    # pad/截取到 2 秒
    target = sample_rate * 2
    if len(audio) < target:
        audio = np.pad(audio, (0, target - len(audio)))
    else:
        audio = audio[:target]

    # 提取特征
    features = compute_mel_features(audio, sample_rate)
    features = features.reshape(1, -1)

    # 推理
    out = _session.run(None, {"input": features})
    # out[1] 是概率字典列表 [{0: prob_neg, 1: prob_pos}]
    probs = out[1][0]
    prob_positive = probs.get(1, 0.0)

    return float(prob_positive)


def get_threshold() -> float:
    if _config is None:
        _load()
    return (_config or {}).get("threshold", 0.7)
