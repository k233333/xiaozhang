"""结构化日志

每次调用入口生成一个 trace_id 注入 contextvar，下游所有日志自动携带该字段。
开发期：彩色控制台；生产期：JSON 文件。
"""
from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

from src.core.config import settings

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    """生成新 trace_id 并绑定到当前上下文"""
    tid = uuid.uuid4().hex[:8]
    _trace_id.set(tid)
    bind_contextvars(trace_id=tid)
    return tid


def clear_trace() -> None:
    _trace_id.set(None)
    clear_contextvars()


def setup_logging() -> None:
    """初始化全局 structlog + stdlib logging。幂等。"""
    log_level = getattr(logging, settings.app.log_level.upper(), logging.INFO)

    logs_dir = settings.resolve_path(settings.paths.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # stdlib logging：同时输出到控制台和文件
    file_handler = logging.FileHandler(
        logs_dir / "xiaozhang.log", encoding="utf-8"
    )
    stream_handler = logging.StreamHandler(sys.stderr)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[stream_handler, file_handler],
    )

    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def log_path() -> Path:
    return settings.resolve_path(settings.paths.logs_dir) / "xiaozhang.log"
