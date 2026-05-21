# coding: utf-8
"""小张技能命令行接口 — 供 Hermes agent 通过 terminal 工具调用。

用法（Hermes 在 bash/PowerShell 里执行）：
    python xz.py douyin-search <关键词>       # 打开抖音搜索并播放最新视频
    python xz.py open-app <app名>             # 打开应用（chrome/wechat/steam/...）
    python xz.py system <动作>               # 系统操作（screenshot/lock/mute/...）
    python xz.py run-turn <任意文字>          # 走完整 小张 run_turn 链路

所有操作底层使用已验证的 pyautogui / pywinauto 代码，与 小张 console 完全一致。
"""
from __future__ import annotations

import sys
import os

# 确保 xiaozhang 包可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _toast(text: str) -> None:
    """弹出右下角气泡（静默失败）"""
    try:
        from src.ui.toast import show_reply
        show_reply(text)
    except Exception:
        pass


def cmd_douyin_search(keyword: str) -> int:
    """抖音搜索并播放最新视频"""
    _toast(f"正在搜索「{keyword}」…")
    from src.actions.douyin_actions import search_play_latest
    ok = search_play_latest(keyword)
    if ok:
        _toast(f"已播放「{keyword}」最新视频")
        print(f"[OK] 抖音已搜索'{keyword}'并播放最新视频")
        return 0
    else:
        _toast("搜索失败")
        print(f"[FAIL] 抖音搜索'{keyword}'失败", file=sys.stderr)
        return 1


def cmd_open_app(app: str) -> int:
    """打开应用，支持名称或路径"""
    import subprocess
    import yaml
    from pathlib import Path

    _toast(f"正在打开「{app}」…")

    apps_file = Path(__file__).parent / "config" / "apps.yaml"
    app_lower = app.lower().strip()

    if apps_file.exists():
        data = yaml.safe_load(apps_file.read_text(encoding="utf-8")) or {}
        apps = data.get("apps", {})
        for name, info in apps.items():
            aliases = [name.lower()] + [a.lower() for a in info.get("aliases", [])]
            if app_lower in aliases:
                uri = info.get("uri")
                path = info.get("path")
                if uri:
                    subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
                    _toast(f"已打开 {name}")
                    print(f"[OK] 通过URI打开: {uri}")
                    return 0
                if path:
                    subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
                    _toast(f"已打开 {name}")
                    print(f"[OK] 通过路径打开: {path}")
                    return 0

    # 找不到时直接尝试 Start-Process
    subprocess.Popen(["powershell", "-Command", f"Start-Process '{app}'"], shell=False)
    _toast(f"已打开 {app}")
    print(f"[OK] Start-Process {app}")
    return 0


def cmd_system(action: str) -> int:
    """系统操作"""
    import subprocess
    action = action.lower().strip()

    if action in ("screenshot", "截图"):
        subprocess.Popen(["powershell", "-Command", "Start-Process 'ms-screenclip:'"])
        _toast("截图工具已启动")
        print("[OK] 截图工具已启动")

    elif action in ("lock", "锁屏"):
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        print("[OK] 锁屏")

    elif action in ("mute", "静音"):
        import ctypes
        VK_VOLUME_MUTE = 0xAD
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
        _toast("静音切换")
        print("[OK] 静音切换")

    elif action in ("volume-up", "音量加", "调大声"):
        import ctypes
        VK_VOLUME_UP = 0xAF
        for _ in range(3):
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
        _toast("音量 +3")
        print("[OK] 音量+3")

    elif action in ("volume-down", "音量减", "调小声"):
        import ctypes
        VK_VOLUME_DOWN = 0xAE
        for _ in range(3):
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
        _toast("音量 -3")
        print("[OK] 音量-3")

    elif action in ("play-pause", "播放暂停"):
        import ctypes
        VK_MEDIA_PLAY_PAUSE = 0xB3
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
        print("[OK] 播放/暂停")

    elif action in ("show-desktop", "显示桌面"):
        import ctypes
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)   # Win
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)   # D
        ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
        _toast("显示桌面")
        print("[OK] 显示桌面")

    else:
        print(f"[UNKNOWN] 不支持的系统操作: {action}", file=sys.stderr)
        print("支持: screenshot/lock/mute/volume-up/volume-down/play-pause/show-desktop")
        return 1

    return 0


def cmd_run_turn(text: str) -> int:
    """走完整 小张 run_turn 链路（含 skill 匹配 + LLM 规划 + 执行 + 学习）"""
    import asyncio
    from src.ui.toast import show_toast
    from src.core.logger import setup_logging
    from src.memory import store
    from src.runtime import run_turn

    setup_logging()
    store.init_db()
    show_toast(text)
    result = asyncio.run(run_turn(text))
    if result.success:
        _toast("好的，已完成")
        print(f"[OK] {result.note or '执行成功'}")
        return 0
    else:
        _toast("抱歉，执行失败了")
        print(f"[FAIL] {result.note or '执行失败'}", file=sys.stderr)
        return 1


def print_help():
    print("""小张技能命令行 (xz.py)
用法:
  python xz.py douyin-search <关键词>    搜索抖音并播放最新视频
  python xz.py open-app <应用名>         打开应用 (chrome/wechat/steam/vscode...)
  python xz.py system <操作>            系统操作 (screenshot/lock/mute/volume-up...)
  python xz.py run-turn <文字>          完整链路执行（含LLM规划+自动学习）

示例:
  python xz.py douyin-search 不惑兄弟
  python xz.py open-app chrome
  python xz.py open-app 微信
  python xz.py system screenshot
  python xz.py run-turn 打开计算器
""")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    cmd = args[0].lower()
    rest = " ".join(args[1:]).strip()

    if cmd == "douyin-search":
        if not rest:
            print("[ERROR] 请提供搜索关键词，例如: python xz.py douyin-search 不惑兄弟", file=sys.stderr)
            return 1
        return cmd_douyin_search(rest)

    elif cmd == "open-app":
        if not rest:
            print("[ERROR] 请提供应用名，例如: python xz.py open-app chrome", file=sys.stderr)
            return 1
        return cmd_open_app(rest)

    elif cmd == "system":
        if not rest:
            print("[ERROR] 请提供系统操作，例如: python xz.py system screenshot", file=sys.stderr)
            return 1
        return cmd_system(rest)

    elif cmd == "run-turn":
        if not rest:
            print("[ERROR] 请提供文字指令，例如: python xz.py run-turn 打开计算器", file=sys.stderr)
            return 1
        return cmd_run_turn(rest)

    else:
        print(f"[ERROR] 未知命令: {cmd}", file=sys.stderr)
        print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
