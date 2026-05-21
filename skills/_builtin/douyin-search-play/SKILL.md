---

name: douyin-search-play

description: 在抖音客户端搜索并播放第一个视频

argument-hint: '[搜索关键词]'

allowed-tools:

  - launch_app

  - wait

  - keys

  - type

  - click

---



# douyin-search-play



## triggers

- 抖音搜

- 在抖音搜

- 打开抖音搜

- 抖音找

- 看抖音的

- 我想看不惑兄弟

- 不惑兄弟



## description

打开抖音客户端 → 点击搜索 → 输入关键词 → 搜索 → 点击第一个视频播放。

使用 pyautogui 键鼠操作（确定性，不依赖 Vision）。



## confirm_required

false



## steps

```json

[

  {"tier": "D", "action": "launch_app", "cmd": ["cmd", "/c", "start", "", "C:\\Users\\k9211\\Desktop\\抖音.lnk"], "description": "打开抖音客户端"},

  {"tier": "D", "action": "wait", "timeout_seconds": 5, "description": "等抖音加载"},

  {"tier": "D", "action": "keys", "keys": "escape", "description": "关闭可能的弹窗"},

  {"tier": "D", "action": "wait", "timeout_seconds": 1}

]

```



## learned

- 抖音 Windows 客户端是 Chrome PWA（Chrome_WidgetWin_1），窗口标题"抖音"

- 窗口位置约 (192,81) 大小 3456x1926

- 顶部导航栏"搜索"在窗口左侧约 300px，距顶 50px

- 搜索框在顶部中间，距顶 45px

- 搜索结果第一个视频在窗口左 1/4，垂直中间位置

- 中文输入用 pyperclip + Ctrl+V（pyautogui.write 不支持中文）

- 搜索后等 5 秒让结果加载

- 确定性坐标操作比 Vision 更可靠（Vision 在 4K 屏上坐标不准）

