---
name: open-feishu
description: 打开飞书
allowed-tools:
  - launch_app
---

# open-feishu

## triggers
- 打开飞书
- 启动飞书
- 飞书
- Lark

## description
通过 lark:// 协议唤起飞书客户端。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "lark://", "description": "唤起飞书", "fallback_tier": "C"}
]
```
