---
name: open-chrome
description: 打开 Chrome 浏览器
allowed-tools:
  - launch_app
---

# open-chrome

## triggers
- 打开Chrome
- 打开 Chrome
- 打开谷歌浏览器
- 启动Chrome
- Chrome

## description
启动 Chrome。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["chrome.exe"], "description": "启动 Chrome", "fallback_tier": "C"}
]
```
