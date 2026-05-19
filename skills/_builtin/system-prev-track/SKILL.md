---
name: system-prev-track
description: 上一首
allowed-tools:
  - keys
---

# system-prev-track

## triggers
- 上一首
- 上一曲
- 退一首

## description
媒体键"上一首"。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "prevtrack", "description": "上一首"}
]
```
