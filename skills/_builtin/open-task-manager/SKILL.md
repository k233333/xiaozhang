---
name: open-task-manager
description: 打开任务管理器
allowed-tools:
  - launch_app
---

# open-task-manager

## triggers
- 打开任务管理器
- 任务管理器
- 启动任务管理器

## description
启动 Windows 任务管理器（taskmgr.exe）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["taskmgr.exe"], "description": "打开任务管理器"}
]
```
