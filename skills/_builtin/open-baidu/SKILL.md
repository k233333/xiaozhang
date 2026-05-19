---
name: open-baidu
description: 在默认浏览器打开百度
allowed-tools:
  - open_url
---

# open-baidu

## triggers
- 打开百度
- 百度
- 百度一下

## description
默认浏览器打开 baidu.com。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://www.baidu.com", "description": "打开百度"}
]
```
