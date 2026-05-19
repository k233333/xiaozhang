"""用户画像（USER.md）

简单的 markdown 文件，由 LLM 周期性更新。
本模块只提供读写接口，更新逻辑在 recall.py。
"""
from __future__ import annotations

from pathlib import Path

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


def _path() -> Path:
    p = settings.resolve_path(settings.paths.user_profile)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


DEFAULT_PROFILE = """# 用户画像

> 由小张运行时自动维护。每个 N 次会话后由 LLM 摘要更新一次。

## 基础信息
- 用户名：k9211
- 系统：Windows
- 平台：桌面

## 偏好（待学习）
- 浏览器：未知
- 视频平台：未知
- 即时通讯：未知

## 语言习惯
- 中文为主，可能夹杂少量英文
"""


def read() -> str:
    p = _path()
    if not p.exists():
        p.write_text(DEFAULT_PROFILE, encoding="utf-8")
        log.info("初始化用户画像", path=str(p))
    return p.read_text(encoding="utf-8")


def write(content: str) -> None:
    _path().write_text(content, encoding="utf-8")
    log.info("更新用户画像", chars=len(content))
