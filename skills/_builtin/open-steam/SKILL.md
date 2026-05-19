---
name: open-steam
description: 打开 Steam 客户端
allowed-tools:
  - launch_app
---

# open-steam

## triggers
- 打开Steam
- 打开 steam
- 启动Steam
- Steam

## description
通过 steam:// 协议唤起 Steam 客户端。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "steam://open/main", "description": "唤起 Steam", "fallback_tier": "C"}
]
```
