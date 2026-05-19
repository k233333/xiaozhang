---
name: system-show-desktop
description: 显示桌面（Win+D）
allowed-tools:
  - keys
---

# system-show-desktop

## triggers
- 显示桌面
- 回到桌面
- 最小化所有
- 切到桌面

## description
按 Win+D 显示桌面。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "win+d", "description": "显示桌面"}
]
```
