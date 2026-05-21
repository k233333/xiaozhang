# coding: utf-8
"""桌面右下角气泡通知 — 显示语音识别文字 & 简短回复

特性：
- 暗色半透明风格
- 出现在屏幕右下角，不抢焦点
- **永远在最上层**（定时 lift + topmost，不会被任何窗口盖住）
- 文字过长自动截断（不会崩溃/溢出屏幕）
- 滑入 → 驻留 3s → 淡出
- 在独立进程中运行，不阻塞主线程
- show_reply() 用于简短回复（"好的"/"已打开"等）

用法：
    from src.ui.toast import show_toast, show_reply
    show_toast("我想看不惑兄弟")           # 显示用户语音
    show_reply("好的，正在打开抖音")        # 显示回复
"""
from __future__ import annotations

import multiprocessing
import sys
import time

# 最大显示字符数（超出截断 + 省略号）
_MAX_TEXT_LEN = 80
# 窗口最大宽度/高度限制
_MAX_W = 420
_MAX_H = 160


def _run_toast(
    text: str,
    duration: float = 3.0,
    title: str = "小张",
    style: str = "user",  # "user" = 用户语音, "reply" = 系统回复
) -> None:
    """在独立进程中创建并显示 toast 窗口。"""
    import tkinter as tk

    # Windows 高 DPI 修复：声明进程 DPI 感知，避免字体模糊
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Win8 fallback
        except Exception:
            pass

    # 防御：空文字 / None
    if not text or not text.strip():
        return

    # 截断过长文本
    display_text = text.strip()
    if len(display_text) > _MAX_TEXT_LEN:
        display_text = display_text[:_MAX_TEXT_LEN - 1] + "…"

    # --- 配色方案 ---
    if style == "reply":
        bg_color = "#0d2137"
        indicator_color = "#4fc3f7"
        text_color = "#b3e5fc"
        font_size = 12
    else:  # user
        bg_color = "#1a1a2e"
        indicator_color = "#00d4aa"
        text_color = "#e6f1ff"
        font_size = 13

    # --- 窗口创建 ---
    try:
        root = tk.Tk()
    except Exception:
        return  # 无图形环境（服务模式），静默退出

    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)  # 初始透明，滑入时渐显
    root.configure(bg=bg_color)

    # 不抢焦点（Windows toolwindow 不出现在任务栏）
    try:
        root.wm_attributes("-toolwindow", True)
    except tk.TclError:
        pass

    # --- 布局 ---
    pad_x, pad_y = 18, 12

    # 标题行
    title_frame = tk.Frame(root, bg=bg_color)
    title_frame.pack(fill="x", padx=pad_x, pady=(pad_y, 0))

    indicator = tk.Label(title_frame, text="●", fg=indicator_color, bg=bg_color,
                         font=("Segoe UI", 8))
    indicator.pack(side="left")

    title_suffix = "听到" if style == "user" else "回复"
    title_label = tk.Label(title_frame, text=f"{title} · {title_suffix}",
                           fg="#8892b0", bg=bg_color,
                           font=("Microsoft YaHei UI", 8))
    title_label.pack(side="left", padx=(5, 0))

    # 正文
    msg_label = tk.Label(
        root,
        text=display_text,
        fg=text_color,
        bg=bg_color,
        font=("Microsoft YaHei UI", font_size, "bold"),
        wraplength=min(340, _MAX_W - pad_x * 2),
        justify="left",
        anchor="w",
    )
    msg_label.pack(fill="x", padx=pad_x, pady=(6, pad_y))

    # --- 尺寸计算 & 定位到右下角 ---
    root.update_idletasks()
    w = min(max(msg_label.winfo_reqwidth() + pad_x * 2 + 10, 240), _MAX_W)
    h = min(title_frame.winfo_reqheight() + msg_label.winfo_reqheight() + pad_y * 2 + 6, _MAX_H)

    scr_w = root.winfo_screenwidth()
    scr_h = root.winfo_screenheight()

    # 右下角，避开任务栏（约 50px）
    x = scr_w - w - 16
    y = scr_h - h - 60

    start_y = y + 25  # 滑入起点

    root.geometry(f"{w}x{h}+{x}+{start_y}")

    # --- 保持永远在最上层 ---
    def keep_on_top():
        try:
            root.attributes("-topmost", False)
            root.attributes("-topmost", True)
            root.lift()
            root.after(500, keep_on_top)  # 每 500ms 刷新一次置顶
        except tk.TclError:
            pass  # 窗口已销毁

    # --- 动画 ---
    def slide_in(step=0):
        if step <= 10:
            progress = step / 10
            current_y = int(start_y - (start_y - y) * progress)
            alpha = 0.92 * progress
            try:
                root.geometry(f"{w}x{h}+{x}+{current_y}")
                root.attributes("-alpha", alpha)
            except tk.TclError:
                return
            root.after(18, slide_in, step + 1)
        else:
            root.attributes("-alpha", 0.92)
            keep_on_top()  # 开始置顶循环
            root.after(int(duration * 1000), fade_out)

    def fade_out(alpha=0.92):
        if alpha > 0.05:
            try:
                root.attributes("-alpha", alpha)
            except tk.TclError:
                return
            root.after(25, fade_out, alpha - 0.07)
        else:
            try:
                root.destroy()
            except Exception:
                pass

    slide_in()

    try:
        root.mainloop()
    except Exception:
        pass  # 防止任何异常导致进程崩溃


def show_toast(text: str, duration: float = 3.0, title: str = "小张") -> None:
    """非阻塞地显示右下角气泡 — 用户语音识别文字。

    Args:
        text: 语音识别文字
        duration: 驻留秒数
        title: 气泡标题
    """
    if not text or not text.strip():
        return
    p = multiprocessing.Process(
        target=_run_toast,
        args=(text, duration, title, "user"),
        daemon=True,
    )
    p.start()


def show_reply(text: str, duration: float = 2.5, title: str = "小张") -> None:
    """非阻塞地显示右下角气泡 — 系统简短回复。

    用于"好的" / "已打开" / "正在搜索…" 等反馈。
    播放音频时不要调用此函数（由调用方控制）。

    Args:
        text: 回复文字
        duration: 驻留秒数（回复默认短一点）
        title: 气泡标题
    """
    if not text or not text.strip():
        return
    p = multiprocessing.Process(
        target=_run_toast,
        args=(text, duration, title, "reply"),
        daemon=True,
    )
    p.start()


# 命令行测试
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Toast 气泡测试")
    parser.add_argument("text", nargs="*", default=["我想看不惑兄弟"])
    parser.add_argument("--reply", action="store_true", help="显示回复风格")
    args = parser.parse_args()

    msg = " ".join(args.text)
    if args.reply:
        show_reply(msg)
    else:
        show_toast(msg)
    time.sleep(4)
