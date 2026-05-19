---
name: open-douyin
description: 打开抖音客户端
allowed-tools:
  - launch_app
---

# open-douyin

## triggers
- 打开抖音
- 抖音
- 看抖音
- 启动抖音
- 抖音客户端

## description
通过桌面快捷方式打开抖音 Windows 客户端。

## confirm_required
false

## steps
```json
[
  {
    "tier": "D",
    "action": "launch_app",
    "cmd": ["cmd", "/c", "start", "", "C:\\Users\\k9211\\Desktop\\抖音.lnk"],
    "description": "打开抖音客户端"
  }
]
```

## learned
- 用户桌面有抖音快捷方式：C:\Users\k9211\Desktop\抖音.lnk
- 用 cmd /c start "" "path.lnk" 可以打开 .lnk 快捷方式
- 客户端比网页版更稳定，不会被反爬
