---
name: open-wechat
description: 唤起微信桌面客户端
allowed-tools:
  - launch_app
---

# open-wechat

## triggers
- 打开微信
- 启动微信
- 微信
- WeChat

## description
通过 weixin:// 协议唤起本地微信。如果未注册协议则降级到直接路径启动。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "weixin://", "description": "通过协议唤起微信", "fallback_tier": "C"}
]
```

## learned
- 微信桌面版必须先打开过一次才能注册 weixin:// 协议
- C 级降级时可用 `tasklist` 找 WeChat.exe，再用 pywinauto 切到前台
