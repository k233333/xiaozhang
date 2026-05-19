---
name: open-telegram
description: 通过 tg:// URI scheme 唤起 Telegram 桌面客户端
allowed-tools:
  - launch_app
---

# open-telegram

## triggers
- 打开电报
- 打开 Telegram
- telegram
- 电报

## description
通过 tg:// 协议唤起本地 Telegram Desktop。

## confirm_required
false

## steps
```json
[
  {
    "tier": "D",
    "action": "launch_app",
    "url": "tg://",
    "description": "唤起 Telegram"
  }
]
```

## learned
- tg:// 协议在 Windows 注册表写入需 Telegram Desktop 已安装并运行过一次
