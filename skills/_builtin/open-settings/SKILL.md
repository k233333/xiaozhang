---
name: open-settings
description: 打开 Windows 设置
allowed-tools:
  - launch_app
---

# open-settings

## triggers
- 打开设置
- 打开Windows设置
- 系统设置

## description
通过 ms-settings: 协议打开 Windows 设置。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "ms-settings:", "description": "打开 Windows 设置"}
]
```
