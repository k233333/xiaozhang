# coding: utf-8
"""将 STT 识别文本转发给本地 Hermes agent 执行。

调用方式：
    result = await dispatch_to_hermes("打开微信")

Hermes 执行 `hermes -z "<text>"` oneshot 模式，stdout 捕获后返回。
超时 120s（LLM 响应 + 执行时间），确保不阻塞主循环。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass

from src.core.logger import get_logger

log = get_logger(__name__)

# hermes 可执行路径默认值（优先 config，其次 PATH）
_HERMES_DEFAULT_EXE = r"D:\11111begin\hermes-agent\venv\Scripts\hermes.exe"
_HERMES_DEFAULT_CWD = r"D:\11111begin\hermes-agent"
_HERMES_TIMEOUT = 120  # 秒


def _hermes_config():
    """从 settings 读取 hermes 配置，失败时返回默认值字典。"""
    try:
        from src.core.config import settings
        cfg = settings.hermes
        return {
            "exe": cfg.exe_path,
            "cwd": cfg.cwd,
            "timeout": cfg.timeout_seconds,
        }
    except Exception:
        return {"exe": _HERMES_DEFAULT_EXE, "cwd": _HERMES_DEFAULT_CWD, "timeout": _HERMES_TIMEOUT}


def _find_hermes() -> str | None:
    """找到 hermes 可执行文件路径。"""
    import os
    exe = _hermes_config()["exe"]
    if os.path.isfile(exe):
        return exe
    return shutil.which("hermes")


@dataclass
class HermesResult:
    success: bool
    output: str
    error: str = ""


async def dispatch_to_hermes(text: str) -> HermesResult:
    """将用户文本转发给 Hermes oneshot 模式执行，返回执行结果。"""
    hermes_exe = _find_hermes()
    if not hermes_exe:
        log.error("Hermes 未找到，请确认 venv 安装", path=_hermes_config()["exe"])
        return HermesResult(success=False, output="", error="hermes not found")

    cfg = _hermes_config()
    cmd = [hermes_exe, "-z", text]
    log.info("转发到 Hermes", text=text, exe=hermes_exe)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cfg["cwd"],
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=cfg["timeout"]
            )
        except asyncio.TimeoutError:
            proc.kill()
            log.warning("Hermes 执行超时", timeout=cfg["timeout"], text=text)
            return HermesResult(success=False, output="", error=f"timeout after {cfg['timeout']}s")

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode == 0:
            log.info("Hermes 执行成功", output_len=len(out))
            return HermesResult(success=True, output=out)
        else:
            log.warning("Hermes 返回非零", returncode=proc.returncode, stderr=err[:200])
            return HermesResult(success=False, output=out, error=err[:500])

    except Exception as e:  # noqa: BLE001
        log.exception("Hermes 调度异常", err=str(e))
        return HermesResult(success=False, output="", error=str(e))
