---
name: system-mute
description: 静音/取消静音（按音量静音键）
allowed-tools:
  - keys
---

# system-mute

## triggers
- 静音
- 取消静音
- 关声音
- 开声音

## description
模拟按下"音量静音"键（Windows VK_VOLUME_MUTE）。再按一次即取消静音。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "volumemute", "description": "切换静音"}
]
```
