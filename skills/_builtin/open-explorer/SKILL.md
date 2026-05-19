---
name: open-explorer
description: 打开文件资源管理器
allowed-tools:
  - launch_app
---

# open-explorer

## triggers
- 打开文件资源管理器
- 打开资源管理器
- 打开文件管理器
- 打开我的电脑
- 打开此电脑

## description
启动 Windows 文件资源管理器。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["explorer.exe"], "description": "打开资源管理器"}
]
```
