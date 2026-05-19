---
name: system-play-pause
description: 暂停/播放（媒体键）
allowed-tools:
  - keys
---

# system-play-pause

## triggers
- 暂停
- 播放
- 暂停播放
- 暂停音乐
- 播放音乐
- 暂停视频
- 播放视频

## description
模拟按下"播放/暂停"媒体键。系统级，对当前播放器有效（网易云/Spotify/B 站等都响应）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "playpause", "description": "切换播放/暂停"}
]
```

## learned
- VK_MEDIA_PLAY_PAUSE 在 pyautogui 里写 'playpause'
- 全局快捷键，不需要焦点对齐播放器
