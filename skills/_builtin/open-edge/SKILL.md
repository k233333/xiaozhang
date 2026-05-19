---
name: open-edge
description: 打开 Edge 浏览器
allowed-tools:
  - launch_app
---

# open-edge

## triggers
- 打开Edge
- 打开 Edge
- 打开微软浏览器
- 启动Edge

## description
启动 Microsoft Edge。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["msedge.exe"], "description": "启动 Edge", "fallback_tier": "C"}
]
```
