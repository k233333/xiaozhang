---
name: open-qq
description: 唤起 QQ 客户端
allowed-tools:
  - launch_app
---

# open-qq

## triggers
- 打开QQ
- 打开 Q Q
- 启动QQ
- QQ

## description
通过 tencent:// 协议唤起 QQ。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "tencent://message/", "description": "唤起 QQ 主面板"}
]
```
