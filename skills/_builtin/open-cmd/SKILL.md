---
name: open-cmd
description: 打开命令提示符
allowed-tools:
  - launch_app
---

# open-cmd

## triggers
- 打开命令行
- 打开命令提示符
- 打开cmd
- 启动cmd
- cmd

## description
启动 Windows 命令提示符。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["cmd.exe"], "description": "打开命令行"}
]
```
