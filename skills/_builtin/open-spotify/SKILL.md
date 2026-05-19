---
name: open-spotify
description: 打开 Spotify
allowed-tools:
  - launch_app
---

# open-spotify

## triggers
- 打开Spotify
- 打开 spotify
- Spotify
- spotify

## description
通过 spotify:// 协议唤起 Spotify 客户端。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "spotify://", "description": "唤起 Spotify", "fallback_tier": "C"}
]
```
