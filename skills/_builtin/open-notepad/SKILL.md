---
name: open-notepad
description: 打开 Windows 记事本
allowed-tools:
  - launch_app
---

# open-notepad

## triggers
- 打开记事本
- 启动记事本
- 运行记事本
- 记事本

## description
启动 Windows 记事本（notepad.exe）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["notepad.exe"], "description": "启动记事本", "fallback_tier": "C"}
]
```

## learned
- D 级直接 launch 即可
- 失败时 C 级走 Win+R → 输入 notepad → Enter
