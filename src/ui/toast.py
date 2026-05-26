# coding: utf-8
"""桌面右下角状态气泡 — 单例持久窗口，任务期间常驻并实时更新状态。

架构：
  - 独立后台进程运行 tkinter 窗口（不阻塞主进程）
  - 主进程通过 multiprocessing.Queue 发送更新指令
  - 气泡在任务处理期间常驻，任务完成后自动淡出

状态流：
  唤醒词触发 → show_listening()     "正在听…"（绿色，常驻）
  ASR 完成   → show_user(text)      显示识别文字（常驻）
  CC 调用中  → show_status(msg)     "正在处理…"（蓝色，常驻）
  任务完成   → show_reply(text)     显示结果（3s 后淡出）
  出错       → show_error(msg)      显示错误（3s 后淡出）

用法：
    from src.ui.toast import show_listening, show_user, show_status, show_reply, show_error, dismiss
"""
from __future__ import annotations

import multiprocessing
import time
from typing import Literal

# 消息类型
MsgType = Literal["listening", "user", "status", "reply", "error", "dismiss"]

# 全局 Queue 和进程（懒初始化）
_queue: multiprocessing.Queue | None = None
_proc: multiprocessing.Process | None = None

_MAX_TEXT_LEN = 80
_MAX_W = 420


# ─────────────────────────────────────────────
# 后台进程：运行 tkinter 窗口
# ─────────────────────────────────────────────

def _toast_process(q: multiprocessing.Queue) -> None:
    """在独立进程中运行持久气泡窗口，从 Queue 接收更新指令。"""
    import tkinter as tk

    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    # ── 配色 ──
    STYLES = {
        "listening": {"bg": "#0a1628", "indicator": "#00d4aa", "text": "#e6f1ff",
                      "label": "小张 · 在听", "font_size": 13},
        "user":      {"bg": "#1a1a2e", "indicator": "#00d4aa", "text": "#e6f1ff",
                      "label": "小张 · 听到", "font_size": 13},
        "status":    {"bg": "#0d2137", "indicator": "#4fc3f7", "text": "#b3e5fc",
                      "label": "小张 · 处理中", "font_size": 12},
        "reply":     {"bg": "#0d2137", "indicator": "#4fc3f7", "text": "#b3e5fc",
                      "label": "小张 · 回复", "font_size": 12},
        "error":     {"bg": "#2d0a0a", "indicator": "#ff5252", "text": "#ffcdd2",
                      "label": "小张 · 出错", "font_size": 12},
    }

    try:
        root = tk.Tk()
    except Exception:
        return

    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(bg="#1a1a2e")
    try:
        root.wm_attributes("-toolwindow", True)
    except tk.TclError:
        pass

    pad_x, pad_y = 18, 12

    title_frame = tk.Frame(root, bg="#1a1a2e")
    title_frame.pack(fill="x", padx=pad_x, pady=(pad_y, 0))

    indicator_lbl = tk.Label(title_frame, text="●", fg="#00d4aa", bg="#1a1a2e",
                             font=("Segoe UI", 8))
    indicator_lbl.pack(side="left")

    title_lbl = tk.Label(title_frame, text="小张 · 在听",
                         fg="#8892b0", bg="#1a1a2e",
                         font=("Microsoft YaHei UI", 8))
    title_lbl.pack(side="left", padx=(5, 0))

    msg_lbl = tk.Label(root, text="", fg="#e6f1ff", bg="#1a1a2e",
                       font=("Microsoft YaHei UI", 13, "bold"),
                       wraplength=min(340, _MAX_W - pad_x * 2),
                       justify="left", anchor="w")
    msg_lbl.pack(fill="x", padx=pad_x, pady=(6, pad_y))

    # 状态：visible=True 表示窗口已滑入
    state = {"visible": False, "alpha": 0.0, "dismiss_after": None}

    def _reposition():
        root.update_idletasks()
        w = min(max(msg_lbl.winfo_reqwidth() + pad_x * 2 + 10, 240), _MAX_W)
        h = title_frame.winfo_reqheight() + msg_lbl.winfo_reqheight() + pad_y * 2 + 6
        h = min(h, 160)
        scr_w = root.winfo_screenwidth()
        scr_h = root.winfo_screenheight()
        x = scr_w - w - 16
        y = scr_h - h - 60
        root.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_style(style_key: str, text: str):
        s = STYLES.get(style_key, STYLES["status"])
        bg = s["bg"]
        root.configure(bg=bg)
        title_frame.configure(bg=bg)
        indicator_lbl.configure(fg=s["indicator"], bg=bg)
        title_lbl.configure(text=s["label"], bg=bg)
        display = text.strip()
        if len(display) > _MAX_TEXT_LEN:
            display = display[:_MAX_TEXT_LEN - 1] + "…"
        msg_lbl.configure(
            text=display,
            fg=s["text"],
            bg=bg,
            font=("Microsoft YaHei UI", s["font_size"], "bold"),
        )
        _reposition()

    def _slide_in(step=0):
        if step <= 10:
            alpha = 0.92 * (step / 10)
            try:
                root.attributes("-alpha", alpha)
            except tk.TclError:
                return
            root.after(18, _slide_in, step + 1)
        else:
            root.attributes("-alpha", 0.92)
            state["visible"] = True
            state["alpha"] = 0.92

    def _fade_out(alpha=0.92):
        if alpha > 0.05:
            try:
                root.attributes("-alpha", alpha)
            except tk.TclError:
                return
            root.after(25, _fade_out, alpha - 0.07)
        else:
            try:
                root.attributes("-alpha", 0.0)
                state["visible"] = False
                state["alpha"] = 0.0
            except tk.TclError:
                pass

    def _keep_on_top():
        try:
            root.attributes("-topmost", False)
            root.attributes("-topmost", True)
            root.lift()
            root.after(500, _keep_on_top)
        except tk.TclError:
            pass

    _keep_on_top()

    def _poll_queue():
        """每 50ms 检查一次 Queue，处理更新指令。"""
        try:
            while not q.empty():
                msg = q.get_nowait()
                if not isinstance(msg, dict):
                    continue

                kind = msg.get("type", "")
                text = msg.get("text", "")

                if kind == "dismiss":
                    if state["visible"]:
                        _fade_out()
                    state["dismiss_after"] = None
                    root.after(100, _poll_queue)
                    return

                # 更新内容
                _apply_style(kind, text)

                # 如果还没显示，滑入
                if not state["visible"]:
                    _slide_in()

                # 决定是否自动消失
                auto_dismiss_ms = msg.get("auto_dismiss_ms", 0)
                if state["dismiss_after"] is not None:
                    root.after_cancel(state["dismiss_after"])
                    state["dismiss_after"] = None

                if auto_dismiss_ms > 0:
                    state["dismiss_after"] = root.after(auto_dismiss_ms, _fade_out)

        except Exception:
            pass
        root.after(50, _poll_queue)

    _poll_queue()

    try:
        root.mainloop()
    except Exception:
        pass


# ─────────────────────────────────────────────
# 主进程 API
# ─────────────────────────────────────────────

def _ensure_running() -> multiprocessing.Queue:
    """确保后台 toast 进程在运行，返回 Queue。"""
    global _queue, _proc
    if _proc is not None and _proc.is_alive():
        return _queue
    # 启动新进程
    _queue = multiprocessing.Queue()
    _proc = multiprocessing.Process(target=_toast_process, args=(_queue,), daemon=True)
    _proc.start()
    time.sleep(0.1)  # 等窗口初始化
    return _queue


def _send(msg: dict) -> None:
    try:
        q = _ensure_running()
        q.put_nowait(msg)
    except Exception:
        pass


def show_listening() -> None:
    """唤醒词触发，显示"正在听…"（常驻，不自动消失）"""
    _send({"type": "listening", "text": "正在听…", "auto_dismiss_ms": 0})


def show_user(text: str) -> None:
    """ASR 识别完成，显示用户说的话（常驻，等待处理结果）"""
    if not text or not text.strip():
        return
    _send({"type": "user", "text": text, "auto_dismiss_ms": 0})


def show_status(text: str) -> None:
    """任务处理中，显示状态信息（常驻）
    例如："正在调用 API…" / "正在执行命令…" / "网络重试中 (2/3)…"
    """
    if not text or not text.strip():
        return
    _send({"type": "status", "text": text, "auto_dismiss_ms": 0})


def show_reply(text: str, duration: float = 3.0) -> None:
    """任务完成，显示结果（duration 秒后自动淡出）"""
    if not text or not text.strip():
        return
    _send({"type": "reply", "text": text, "auto_dismiss_ms": int(duration * 1000)})


def show_error(text: str, duration: float = 4.0) -> None:
    """显示错误信息（duration 秒后自动淡出）"""
    if not text or not text.strip():
        return
    _send({"type": "error", "text": text, "auto_dismiss_ms": int(duration * 1000)})


def dismiss() -> None:
    """立即淡出气泡"""
    _send({"type": "dismiss", "text": ""})


# ── 兼容旧接口 ──
def show_toast(text: str, duration: float = 3.0, title: str = "小张") -> None:
    """兼容旧接口：等同于 show_user"""
    show_user(text)


# 命令行测试
if __name__ == "__main__":
    print("测试气泡状态流...")
    show_listening()
    time.sleep(1.5)
    show_user("帮我重启电脑")
    time.sleep(1.5)
    show_status("正在调用 API…")
    time.sleep(2)
    show_status("网络重试中 (2/3)…")
    time.sleep(2)
    show_reply("好的，已完成重启准备")
    time.sleep(4)
    print("done")
