---
name: system-volume-down
description: 音量-
allowed-tools:
  - keys
---

# system-volume-down

## triggers
- 音量减
- 音量-
- 小点声
- 调小声音

## description
按 5 次 VK_VOLUME_DOWN（每次减 2%）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "volumedown", "description": "音量-"},
  {"tier": "D", "action": "keys", "keys": "volumedown"},
  {"tier": "D", "action": "keys", "keys": "volumedown"},
  {"tier": "D", "action": "keys", "keys": "volumedown"},
  {"tier": "D", "action": "keys", "keys": "volumedown"}
]
```
