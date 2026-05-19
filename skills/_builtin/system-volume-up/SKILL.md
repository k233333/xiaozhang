---
name: system-volume-up
description: 音量+
allowed-tools:
  - keys
---

# system-volume-up

## triggers
- 音量加
- 音量+
- 大点声
- 调大声音

## description
按 5 次 VK_VOLUME_UP（每次加 2%）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "volumeup", "description": "音量+"},
  {"tier": "D", "action": "keys", "keys": "volumeup"},
  {"tier": "D", "action": "keys", "keys": "volumeup"},
  {"tier": "D", "action": "keys", "keys": "volumeup"},
  {"tier": "D", "action": "keys", "keys": "volumeup"}
]
```
