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
    """弹出右下角气泡 + TTS 语音播报（静默失败）"""
    try:
        from src.ui.toast import show_reply
        show_reply(text)
    except Exception:
        pass
    try:
        from src.audio.tts import speak_sync
        speak_sync(text)
    except Exception:
        pass


def cmd_douyin_search(keyword: str) -> int:
    """抖音搜索并播放最新视频"""
    _toast(f"正在搜索「{keyword}」…")
    from src.actions.douyin_actions import search_and_play
    ok = search_and_play(keyword)
    if ok:
        _toast(f"已播放「{keyword}」最新视频")
        print(f"[OK] 抖音已搜索'{keyword}'并播放最新视频")
        return 0
    else:
        _toast("搜索失败")
        print(f"[FAIL] 抖音搜索'{keyword}'失败", file=sys.stderr)
        return 1


def cmd_open_app(app: str) -> int:
    """打开应用 — 自动搜索已安装软件（扫描开始菜单快捷方式）"""
    import subprocess
    from src.utils.app_scanner import search

    _toast(f"正在打开「{app}」…")

    results = search(app)
    if results:
        target = results[0]["target"]
        name = results[0]["name"]
        try:
            subprocess.Popen([target], shell=False)
        except OSError:
            subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
        _toast(f"已打开 {name}")
        print(f"[OK] {name} → {target}")
        return 0

    # 没找到 — 尝试 Start-Process 兜底
    subprocess.Popen(["powershell", "-Command", f"Start-Process '{app}'"], shell=False)
    _toast(f"尝试打开 {app}")
    print(f"[OK] Start-Process {app}（未在索引中找到精确匹配）")
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


def cmd_bilibili_search(keyword: str) -> int:
    """B站搜索并播放第一个视频"""
    import subprocess
    import time

    _toast(f"正在搜索B站「{keyword}」…")
    url = f"https://search.bilibili.com/all?keyword={keyword}"
    try:
        subprocess.Popen(["cmd", "/c", "start", "chrome", url], shell=False)
        print(f"[OK] 已打开B站搜索: {keyword}")
        _toast(f"已打开B站搜索「{keyword}」")
        return 0
    except Exception as e:
        print(f"[FAIL] B站搜索失败: {e}", file=sys.stderr)
        return 1


def cmd_media(action: str) -> int:
    """媒体控制（播放/暂停/上一曲/下一曲）"""
    import ctypes
    action = action.lower().strip()

    key_map = {
        "play-pause": 0xB3,
        "播放暂停": 0xB3,
        "next": 0xB0,
        "下一曲": 0xB0,
        "prev": 0xB1,
        "上一曲": 0xB1,
        "stop": 0xB2,
        "停止": 0xB2,
    }

    vk = key_map.get(action)
    if vk is None:
        print(f"[UNKNOWN] 不支持的媒体操作: {action}", file=sys.stderr)
        print("支持: play-pause/next/prev/stop")
        return 1

    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    print(f"[OK] 媒体操作: {action}")
    return 0


def cmd_search_torrent(query: str) -> int:
    """搜索磁力资源（美剧/电影/动漫）— 自动过滤720p以下+死种"""
    import asyncio
    from src.crawlers.torrent_search import search_all, check_torrent_health

    _toast(f"正在搜索资源「{query}」…")
    print(f"[INFO] 搜索中（自动过滤 <1080p 和死种）: {query}", flush=True)

    results = asyncio.run(search_all(query, limit=5, min_resolution=1080))
    if not results:
        print(f"[FAIL] 未找到「{query}」的 1080p+ 活跃资源", file=sys.stderr)
        print("[HINT] 尝试用英文名搜索，或降低分辨率要求", file=sys.stderr)
        return 1

    print(f"\n[OK] 找到 {len(results)} 个 1080p+ 资源:\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.summary()}")

    # 对最佳结果做健康检查
    best = results[0]
    print(f"\n[CHECK] 正在验证最佳资源的种子健康度...", flush=True)
    health = asyncio.run(check_torrent_health(best.magnet))
    print(f"[HEALTH] {health['note']}")

    if health.get("alive") is False:
        # 最佳是死种，找下一个活的
        print("[WARN] 最佳资源是死种，检查下一个...", flush=True)
        for r in results[1:]:
            h = asyncio.run(check_torrent_health(r.magnet))
            if h.get("alive"):
                best = r
                health = h
                print(f"[HEALTH] 替换为: {r.title[:60]} — {h['note']}")
                break

    print(f"\n[BEST] {best.title}")
    print(f"[BEST_SIZE] {best.size}")
    print(f"[BEST_SEEDS] {best.seeders} (API) / {health.get('seeders', '?')} (实时)")
    print(f"[BEST_MAGNET] {best.magnet}")
    return 0


def cmd_download_magnet(magnet: str) -> int:
    """用迅雷打开磁力链接下载"""
    import subprocess

    if not magnet.startswith("magnet:"):
        print(f"[ERROR] 无效磁力链: {magnet[:50]}", file=sys.stderr)
        return 1

    _toast("正在打开迅雷下载…")
    try:
        # 迅雷支持直接打开磁力链接
        subprocess.Popen(["cmd", "/c", "start", "", magnet], shell=False)
        print(f"[OK] 已发送到迅雷: {magnet[:60]}...")
        return 0
    except Exception as e:
        print(f"[FAIL] 打开迅雷失败: {e}", file=sys.stderr)
        return 1


def cmd_search_pan(query: str) -> int:
    """搜索夸克网盘资源 — 打开搜索页面供 Hermes browser 工具提取"""
    import asyncio
    import subprocess
    from src.crawlers.pan_search import search_quark_all

    _toast(f"正在搜索夸克网盘「{query}」…")
    print(f"[INFO] 搜索夸克网盘: {query}", flush=True)

    # 先尝试 API 搜索
    results = asyncio.run(search_quark_all(query, limit=8))

    if results:
        print(f"\n[OK] 找到 {len(results)} 个夸克网盘资源:\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.summary()}")
            print(f"     链接: {r.url}")
        print()
        best = results[0]
        print(f"[BEST] {best.title}")
        print(f"[BEST_URL] {best.url}")
        if best.password:
            print(f"[BEST_PWD] {best.password}")
        return 0

    # API 全部失败 → 打开浏览器搜索页面（Hermes 可以用 browser 工具提取）
    from urllib.parse import quote_plus as qp
    search_url = f"https://www.bing.com/search?q=site%3Apan.quark.cn+{qp(query)}"
    print(f"[FALLBACK] API 搜索失败，打开浏览器搜索...")
    print(f"[SEARCH_URL] {search_url}")
    try:
        subprocess.Popen(["cmd", "/c", "start", "chrome", search_url], shell=False)
        print(f"[OK] 已打开 Bing 搜索夸克网盘资源，请从结果中选择")
        return 0
    except Exception as e:
        print(f"[FAIL] 打开浏览器失败: {e}", file=sys.stderr)
        return 1


def cmd_news(topic: str) -> int:
    """抓取科技/金融资讯"""
    import asyncio
    from src.crawlers.news_feed import fetch_all_news, fetch_hackernews, fetch_36kr

    topic = topic.lower().strip()
    _toast(f"正在抓取资讯…")

    if topic in ("tech", "科技", "all", "全部", ""):
        results = asyncio.run(fetch_all_news(limit=10))
    elif topic in ("hn", "hackernews", "hacker"):
        results = asyncio.run(fetch_hackernews(limit=10))
    elif topic in ("36kr", "中文", "国内"):
        results = asyncio.run(fetch_36kr(limit=10))
    else:
        results = asyncio.run(fetch_all_news(limit=10))

    if not results:
        print("[FAIL] 资讯抓取失败", file=sys.stderr)
        return 1

    print(f"\n[OK] 今日资讯 ({len(results)} 条):\n")
    for i, item in enumerate(results, 1):
        print(f"  {i}. {item.one_line()}")
        if item.url:
            print(f"     {item.url}")
    print()
    return 0


def print_help():
    print("""小张技能命令行 (xz.py)
用法:
  python xz.py douyin-search <关键词>    搜索抖音并播放最新视频
  python xz.py bilibili-search <关键词>  搜索B站并打开结果
  python xz.py open-app <应用名>         打开应用 (chrome/wechat/steam/vscode...)
  python xz.py system <操作>            系统操作 (screenshot/lock/mute/volume-up...)
  python xz.py media <操作>             媒体控制 (play-pause/next/prev/stop)
  python xz.py search-torrent <关键词>   搜索磁力资源（美剧/电影）
  python xz.py search-pan <关键词>      搜索夸克网盘资源
  python xz.py download <磁力链>         用迅雷下载磁力链接
  python xz.py news [话题]              抓取科技/金融资讯 (tech/36kr/hn)
  python xz.py run-turn <文字>          完整链路执行（含Hermes规划+自动学习）

示例:
  python xz.py search-torrent "White Lotus S03"
  python xz.py search-torrent "白莲花度假村 第三季"
  python xz.py download "magnet:?xt=urn:btih:..."
  python xz.py news tech
  python xz.py news 36kr
  python xz.py douyin-search 不惑兄弟
  python xz.py open-app chrome
  python xz.py system screenshot
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

    elif cmd == "bilibili-search":
        if not rest:
            print("[ERROR] 请提供搜索关键词，例如: python xz.py bilibili-search 原神攻略", file=sys.stderr)
            return 1
        return cmd_bilibili_search(rest)

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

    elif cmd == "media":
        if not rest:
            print("[ERROR] 请提供媒体操作，例如: python xz.py media play-pause", file=sys.stderr)
            return 1
        return cmd_media(rest)

    elif cmd == "search-torrent":
        if not rest:
            print("[ERROR] 请提供搜索关键词，例如: python xz.py search-torrent White Lotus S03", file=sys.stderr)
            return 1
        return cmd_search_torrent(rest)

    elif cmd == "download":
        if not rest:
            print("[ERROR] 请提供磁力链接", file=sys.stderr)
            return 1
        return cmd_download_magnet(rest)

    elif cmd == "search-pan":
        if not rest:
            print("[ERROR] 请提供搜索关键词，例如: python xz.py search-pan 低智商犯罪", file=sys.stderr)
            return 1
        return cmd_search_pan(rest)

    elif cmd == "news":
        return cmd_news(rest or "all")

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
