---
name: open-lol
description: 启动英雄联盟（通过 WeGame）
allowed-tools:
  - launch_app
---

# open-lol

## triggers
- 打开英雄联盟
- 打开LOL
- 打开 lol
- 英雄联盟
- LOL

## description
通过 WeGame 协议启动英雄联盟。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "wegame://rungame/1/0/0", "description": "通过 WeGame 启动 LOL", "fallback_tier": "C"}
]
```

## learned
- wegame://rungame/1/0/0 是英雄联盟的 WeGame 启动协议
- 需要 WeGame 已安装并登录
