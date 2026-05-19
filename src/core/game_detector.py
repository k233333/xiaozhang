"""游戏检测器（4 种方法 + 自学习白名单）

判定优先级（任一命中即认为在玩游戏）：
  1. 用户强制（最高优先级）
  2. 黑名单命中 → 直接判非游戏（OBS 等）
  3. 进程白名单匹配
  4. 独占全屏
  5. GPU 占用持续高
  6. CPU 占用持续高（顺便触发 cpu_guard 高负载保护）

自学习：当 4 或 5 触发但 3 未命中时，记录前台进程进 auto_learned_games。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import psutil

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class DetectionState:
    is_game: bool = False
    matched_method: str = ""
    fg_process: str = ""
    fg_window_title: str = ""
    cpu_high_since: float | None = None
    gpu_high_since: float | None = None
    last_check_ts: float = 0.0
    auto_learned: list[str] = field(default_factory=list)


def _get_foreground_window_info() -> tuple[str, str]:
    try:
        import win32gui  # noqa: PLC0415
        import win32process  # noqa: PLC0415

        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return "", ""
        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            name = ""
        return name, title
    except Exception as e:  # noqa: BLE001
        log.debug("获取前台窗口失败", err=str(e))
        return "", ""


def _is_fullscreen_exclusive() -> bool:
    try:
        import win32api  # noqa: PLC0415
        import win32con  # noqa: PLC0415
        import win32gui  # noqa: PLC0415

        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return False
        cls = win32gui.GetClassName(hwnd)
        if cls in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False

        rect = win32gui.GetWindowRect(hwnd)
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        if (
            rect[0] <= 0 and rect[1] <= 0
            and rect[2] >= screen_w and rect[3] >= screen_h
        ):
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            has_caption = bool(style & win32con.WS_CAPTION)
            return not has_caption
        return False
    except Exception as e:  # noqa: BLE001
        log.debug("全屏检测失败", err=str(e))
        return False


def _gpu_load_pct() -> float:
    """0-100，无法检测返回 -1"""
    try:
        import GPUtil  # noqa: PLC0415
        gpus = GPUtil.getGPUs()
        if gpus:
            return float(gpus[0].load * 100)
    except Exception:  # noqa: BLE001
        pass
    return -1.0


class GameDetector:
    def __init__(self) -> None:
        self.state = DetectionState()
        self._whitelist_cache: set[str] = self._build_whitelist()
        self._blacklist_cache: set[str] = {p.lower() for p in settings.non_game_processes}

    def _build_whitelist(self) -> set[str]:
        wl = {p.lower() for p in settings.game_processes}
        wl.update({p.lower() for p in settings.auto_learned_games})
        return wl

    def reload_whitelist(self) -> None:
        self._whitelist_cache = self._build_whitelist()

    def is_blacklisted(self, proc_name: str) -> bool:
        return proc_name.lower() in self._blacklist_cache

    def check_once(self) -> DetectionState:
        s = self.state
        s.last_check_ts = time.time()
        det = settings.resource_manager.detection
        thresh = settings.resource_manager.thresholds

        # 1. 用户强制
        if settings.resource_manager.force_mode == "gaming":
            s.is_game = True
            s.matched_method = "force_user"
            return s
        if settings.resource_manager.force_mode == "standard":
            s.is_game = False
            s.matched_method = "force_user"
            return s

        fg_name, fg_title = _get_foreground_window_info()
        s.fg_process = fg_name
        s.fg_window_title = fg_title

        # 2. 黑名单
        if fg_name and self.is_blacklisted(fg_name):
            s.is_game = False
            s.matched_method = "blacklist"
            return s

        # 3. 白名单
        if det.by_process_name and fg_name and fg_name.lower() in self._whitelist_cache:
            s.is_game = True
            s.matched_method = "whitelist"
            return s

        # 4. 全屏
        if det.by_fullscreen and _is_fullscreen_exclusive():
            s.is_game = True
            s.matched_method = "fullscreen"
            self._auto_learn(fg_name)
            return s

        # 5. GPU 持续高
        if det.by_gpu_load:
            gpu = _gpu_load_pct()
            if gpu >= 0:
                if gpu > thresh.gpu_busy_percent:
                    if s.gpu_high_since is None:
                        s.gpu_high_since = time.time()
                    elif time.time() - s.gpu_high_since > thresh.gpu_busy_duration_seconds:
                        s.is_game = True
                        s.matched_method = "gpu_load"
                        self._auto_learn(fg_name)
                        return s
                else:
                    s.gpu_high_since = None

        # 6. CPU 持续高
        if det.by_cpu_load:
            cpu = psutil.cpu_percent(interval=0.0)
            if cpu > thresh.cpu_busy_percent:
                if s.cpu_high_since is None:
                    s.cpu_high_since = time.time()
                elif time.time() - s.cpu_high_since > thresh.cpu_busy_duration_seconds:
                    s.is_game = True
                    s.matched_method = "cpu_load"
                    return s
            else:
                s.cpu_high_since = None

        s.is_game = False
        s.matched_method = ""
        return s

    def _auto_learn(self, proc_name: str) -> None:
        if not proc_name:
            return
        if proc_name.lower() in self._whitelist_cache:
            return
        if proc_name.lower() in self._blacklist_cache:
            return

        path = settings.resolve_path(settings.paths.knowledge_runtime)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except json.JSONDecodeError:
            data = {}
        learned: list = data.setdefault("auto_learned_games", [])
        if proc_name not in learned:
            learned.append(proc_name)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._whitelist_cache.add(proc_name.lower())
            log.info("自学习游戏白名单 +1", proc=proc_name, total=len(learned))


detector = GameDetector()
