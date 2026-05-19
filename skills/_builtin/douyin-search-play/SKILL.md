---
name: douyin-search-play
description: 在抖音客户端搜索指定关键词并播放第一个视频
argument-hint: '[搜索关键词]'
allowed-tools:
  - launch_app
  - wait
  - keys
  - type
  - screenshot_and_decide
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
打开抖音客户端 → 搜索关键词 → 点击第一个视频播放。
注意：当前 trigger 匹配后会走 LLM 规划（因为需要提取关键词参数）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["cmd", "/c", "start", "", "C:\\Users\\k9211\\Desktop\\抖音.lnk"], "description": "打开抖音客户端"},
  {"tier": "D", "action": "wait", "timeout_seconds": 4, "description": "等抖音加载"},
  {"tier": "D", "action": "keys", "keys": "escape", "description": "关闭可能的弹窗"},
  {"tier": "D", "action": "wait", "timeout_seconds": 1},
  {"tier": "D", "action": "keys", "keys": "ctrl+f", "description": "打开搜索（如果支持）"},
  {"tier": "D", "action": "wait", "timeout_seconds": 1},
  {"tier": "A", "action": "screenshot_and_decide", "description": "找到搜索框并点击，然后输入'不惑兄弟'并搜索"}
]
```

## learned
- 抖音 Windows 客户端是 Electron 应用（Chrome_WidgetWin_1）
- 窗口标题就是"抖音"
- Ctrl+F 不一定能打开搜索，可能需要点击顶部搜索图标
- 搜索框位置通常在窗口顶部中央
- 如果有弹窗（登录/广告），先按 Escape 关掉
