---
name: open-dingtalk
description: 打开钉钉
allowed-tools:
  - launch_app
---

# open-dingtalk

## triggers
- 打开钉钉
- 启动钉钉
- 钉钉

## description
通过 dingtalk:// 协议唤起钉钉客户端。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "dingtalk://", "description": "唤起钉钉", "fallback_tier": "C"}
]
```
