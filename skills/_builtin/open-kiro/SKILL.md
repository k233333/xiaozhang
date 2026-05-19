---
name: open-kiro
description: 打开 Kiro IDE
allowed-tools:
  - launch_app
---

# open-kiro

## triggers
- 打开Kiro
- 打开 kiro
- 启动Kiro
- Kiro

## description
启动 Kiro IDE。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["Kiro.exe"], "description": "启动 Kiro", "fallback_tier": "C"}
]
```
