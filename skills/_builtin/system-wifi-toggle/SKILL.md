---
name: system-wifi-toggle
description: 打开/关闭 WiFi（通过 ms-settings）
allowed-tools:
  - launch_app
---

# system-wifi-toggle

## triggers
- 打开WiFi设置
- WiFi设置
- 网络设置
- 打开网络

## description
打开 Windows WiFi 设置页面。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "ms-settings:network-wifi", "description": "打开 WiFi 设置"}
]
```
