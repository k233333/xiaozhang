---
name: system-alt-tab
description: 切换窗口（Alt+Tab）
allowed-tools:
  - keys
---

# system-alt-tab

## triggers
- 切换窗口
- 切到上一个窗口
- alt tab

## description
模拟 Alt+Tab 切换到上一个窗口。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "alt+tab", "description": "切换窗口"}
]
```
