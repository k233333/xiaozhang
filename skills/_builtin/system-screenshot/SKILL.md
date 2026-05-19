---
name: system-screenshot
description: 触发 Win+Shift+S 截图工具
allowed-tools:
  - keys
---

# system-screenshot

## triggers
- 截图
- 截屏
- 屏幕截图

## description
按 Win+Shift+S 调出 Windows 截图工具。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "win+shift+s", "description": "调出截图工具"}
]
```
