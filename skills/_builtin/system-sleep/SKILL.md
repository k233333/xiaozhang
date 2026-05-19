---
name: system-sleep
description: 让电脑进入睡眠模式
allowed-tools:
  - run_cmd
---

# system-sleep

## triggers
- 睡眠
- 电脑睡眠
- 休眠

## description
调用 rundll32 让电脑进入睡眠模式。

## confirm_required
true

## steps
```json
[
  {"tier": "D", "action": "run_cmd", "cmd": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"], "description": "进入睡眠", "requires_confirmation": true}
]
```
