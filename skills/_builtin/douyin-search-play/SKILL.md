---
name: douyin-search-play
description: 在抖音客户端搜索创作者/关键词并播放最新视频（含自动开启抖音）
argument-hint: '[搜索关键词或创作者名]'
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
- 搜抖音

## description
自动开启抖音客户端（如未开启）→ 搜索关键词 → 尝试切换「最新」排序 → 点击播放第一个视频。
使用 pyautogui 键鼠操作（本地执行，0 tokens，速度快）。
{KEYWORD} 会被替换为实际命中的触发词。

## confirm_required
false

## steps
```json
[
  {
    "tier": "D",
    "action": "douyin_search_play",
    "text": "{KEYWORD}",
    "description": "搜索并播放最新视频（含自动开启抖音、切换最新tab）",
    "timeout_seconds": 30
  }
]
```

## learned
- 抖音 Windows 客户端是 Chrome PWA（Chrome_WidgetWin_1），窗口标题"抖音"
- _open_douyin() 会先检查窗口是否存在，不存在才启动 lnk，冷启动等 7s
- 搜索框在顶部中间，距顶 45px；中文用 pyperclip + Ctrl+V
- 「最新」Tab 约在窗口高度 14% 处，水平 44% 处（经验值）
- OmniParser 完整实现后会自动识别「最新」按钮坐标，精度更高
- 第一个视频点击位置：左 1/4，垂直 45% 处
