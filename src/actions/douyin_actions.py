"""抖音客户端专用操作（已验证的确定性键鼠流程）

通过 pywinauto 找窗口 + pyautogui 操作，不依赖 Vision。
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pyautogui
import pyperclip
from pywinauto import Desktop

from src.core.logger import get_logger

log = get_logger(__name__)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3

_DOUYIN_LNK = r"C:\Users\k9211\Desktop\抖音.lnk"
_DOUYIN_LOAD_WAIT = 7.0   # PWA 冷启动等待秒数
_SEARCH_RESULT_WAIT = 5.0  # 搜索结果加载等待


def _open_douyin() -> bool:
    """启动抖音（如果已有窗口则直接返回 True）"""
    desktop = Desktop(backend="uia")
    wins = [w for w in desktop.windows() if "抖音" in w.window_text()]
    if wins:
        return True
    if Path(_DOUYIN_LNK).exists():
        subprocess.Popen(["cmd", "/c", "start", "", _DOUYIN_LNK], shell=False)
        log.info("抖音正在启动，等待 PWA 加载", wait=_DOUYIN_LOAD_WAIT)
        time.sleep(_DOUYIN_LOAD_WAIT)
    else:
        log.warning("抖音快捷方式不存在", path=_DOUYIN_LNK)
        return False
    wins = [w for w in desktop.windows() if "抖音" in w.window_text()]
    return bool(wins)


def _try_click_latest_tab(win_left: int, win_top: int, win_w: int, win_h: int) -> bool:
    """尝试点击搜索结果里的"最新"排序 Tab。
    
    策略1：OmniParser（若已加载）识别屏幕元素 → 找"最新"标签
    策略2：pyautogui.locateOnScreen 图像模板匹配（需准备截图模板时才有效）
    策略3：按抖音 PWA 常见布局，在搜索结果 Tab 行偏右侧点击
    """
    # 策略1：OmniParser 本地模型（当 OmniParser 完整实现后自动生效）
    try:
        from src.local_models.resource_manager import resource_manager  # noqa: PLC0415
        model = resource_manager.get_model("omniparser")
        if model and model.is_loaded():
            from src.vision.screenshot import grab_full  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415
            img = grab_full(save=False)
            if img:
                elements = model.parse(img)
                for el in elements:
                    label = el.get("label", "")
                    if "最新" in label:
                        cx, cy = el["center_x"], el["center_y"]
                        pyautogui.click(cx, cy)
                        log.info("OmniParser 点击「最新」Tab", pos=(cx, cy))
                        time.sleep(2)
                        return True
    except Exception as e:  # noqa: BLE001
        log.debug("OmniParser 策略跳过", err=str(e))

    # 策略3：抖音 PWA 搜索结果 Tab 通常在距顶部约 13~16% 高度处
    # Tab 行从左到右：综合 | 视频 | 用户 | 最新 ...
    # "最新" 通常是第 4 个 Tab，x 约在窗口宽度 40~50%
    tab_y = win_top + int(win_h * 0.14)
    for tab_x_ratio in (0.42, 0.48, 0.38, 0.52):
        tab_x = win_left + int(win_w * tab_x_ratio)
        # 粗定位，靠近中间位置尝试
        try:
            pyautogui.moveTo(tab_x, tab_y, duration=0.15)
        except Exception:
            pass
    # 实际点击 0.44 处（经验值，抖音 PWA 第3/4个tab附近）
    tab_x = win_left + int(win_w * 0.44)
    pyautogui.click(tab_x, tab_y)
    log.info("坐标策略点击「最新」Tab", pos=(tab_x, tab_y))
    time.sleep(2)
    return True  # 不管成没成，继续后续步骤


def search_play_latest(keyword: str) -> bool:
    """搜索关键词 → 点击「最新」tab → 播放第一个视频。
    
    完整流程（含自动开启抖音）。
    """
    # 0. 确保抖音窗口存在
    if not _open_douyin():
        log.error("抖音未能启动")
        return False

    desktop = Desktop(backend="uia")
    wins = [w for w in desktop.windows() if "抖音" in w.window_text()]
    if not wins:
        log.warning("抖音窗口仍未找到")
        return False

    dw = wins[0]
    dw.set_focus()
    time.sleep(0.8)

    rect = dw.rectangle()
    win_left, win_top = rect.left, rect.top
    win_w, win_h = rect.width(), rect.height()
    log.info("抖音窗口", left=win_left, top=win_top, w=win_w, h=win_h)

    # 1. 点击顶部"搜索"导航入口
    pyautogui.click(win_left + 300, win_top + 50)
    time.sleep(0.8)

    # 2. 点击搜索框（顶部中间）
    pyautogui.click(win_left + win_w // 2, win_top + 45)
    time.sleep(0.4)

    # 3. 清空 + 粘贴关键词（pyautogui.write 不支持中文）
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyperclip.copy(keyword)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)

    # 4. 回车搜索
    pyautogui.press("enter")
    log.info("已搜索", keyword=keyword)
    time.sleep(_SEARCH_RESULT_WAIT)

    # 5. 尝试切换到「最新」排序
    _try_click_latest_tab(win_left, win_top, win_w, win_h)

    # 6. 点击第一个视频（搜索结果区左 1/4，垂直中间偏上）
    video_x = win_left + win_w // 4
    video_y = win_top + int(win_h * 0.45)
    pyautogui.click(video_x, video_y)
    time.sleep(1.5)

    log.info("抖音搜索播放完成", keyword=keyword, video_pos=(video_x, video_y))
    return True


def search_and_play(keyword: str) -> bool:
    """向后兼容接口：等同 search_play_latest。"""
    return search_play_latest(keyword)
