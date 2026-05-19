---
name: open-youtube
description: 在默认浏览器打开 YouTube
allowed-tools:
  - open_url
---

# open-youtube

## triggers
- 打开YouTube
- 打开 youtube
- 打开油管
- YouTube
- 油管

## description
默认浏览器打开 youtube.com。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://www.youtube.com", "description": "打开 YouTube"}
]
```
