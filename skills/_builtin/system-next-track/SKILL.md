---
name: system-next-track
description: 下一首
allowed-tools:
  - keys
---

# system-next-track

## triggers
- 下一首
- 下一曲
- 切歌

## description
媒体键"下一首"。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "nexttrack", "description": "下一首"}
]
```
