"""抖音客户端专用操作（已验证的确定性键鼠流程）



通过 pywinauto 找窗口 + pyautogui 操作，不依赖 Vision。

"""

from __future__ import annotations



import time



import pyautogui

import pyperclip

from pywinauto import Desktop



from src.core.logger import get_logger



log = get_logger(__name__)



pyautogui.FAILSAFE = False

pyautogui.PAUSE = 0.3





def search_and_play(keyword: str) -> bool:

    """在抖音客户端搜索关键词并播放第一个视频



    返回 True 表示成功执行了所有步骤。

    """

    # 1. 找到抖音窗口

    desktop = Desktop(backend="uia")

    wins = [w for w in desktop.windows() if "抖音" in w.window_text()]

    if not wins:

        log.warning("抖音窗口未找到")

        return False



    dw = wins[0]

    dw.set_focus()

    time.sleep(1)



    rect = dw.rectangle()

    win_left = rect.left

    win_top = rect.top

    win_w = rect.width()

    win_h = rect.height()

    log.info("抖音窗口", left=win_left, top=win_top, w=win_w, h=win_h)



    # 2. 点击顶部"搜索"导航

    search_nav_x = win_left + 300

    search_nav_y = win_top + 50

    pyautogui.click(search_nav_x, search_nav_y)

    time.sleep(1)



    # 3. 点击搜索框

    searchbar_x = win_left + win_w // 2

    searchbar_y = win_top + 45

    pyautogui.click(searchbar_x, searchbar_y)

    time.sleep(0.5)



    # 4. 清空 + 输入关键词

    pyautogui.hotkey("ctrl", "a")

    time.sleep(0.1)

    pyperclip.copy(keyword)

    pyautogui.hotkey("ctrl", "v")

    time.sleep(0.5)



    # 5. Enter 搜索

    pyautogui.press("enter")

    time.sleep(5)  # 等搜索结果加载



    # 6. 点击第一个视频（左 1/4，垂直中间）

    video_x = win_left + win_w // 4

    video_y = win_top + win_h // 2

    pyautogui.click(video_x, video_y)

    time.sleep(2)



    log.info("抖音搜索播放完成", keyword=keyword, click_pos=(video_x, video_y))

    return True

