---
name: open-netease-music
description: 打开网易云音乐
allowed-tools:
  - launch_app
---

# open-netease-music

## triggers
- 打开网易云
- 打开网易云音乐
- 网易云
- 网易云音乐

## description
通过 orpheus:// 协议唤起网易云音乐客户端。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "orpheus://", "description": "唤起网易云音乐", "fallback_tier": "C"}
]
```

## learned
- orpheus:// 是网易云音乐注册的 URI scheme
- 如果协议未注册，C 级可用 tasklist 找 cloudmusic.exe 切前台
