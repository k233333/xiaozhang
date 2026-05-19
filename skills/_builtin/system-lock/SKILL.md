---
name: system-lock
description: 锁屏（不需要二次确认，无副作用）
allowed-tools:
  - run_cmd
---

# system-lock

## triggers
- 锁屏
- 锁定电脑
- 离开
- 我去开会

## description
调用 rundll32 触发 LockWorkStation 锁屏。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "run_cmd", "cmd": ["rundll32.exe", "user32.dll,LockWorkStation"], "description": "锁屏"}
]
```
