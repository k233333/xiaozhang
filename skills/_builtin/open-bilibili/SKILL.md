---
name: open-bilibili
description: 在默认浏览器打开 B 站
allowed-tools:
  - open_url
---

# open-bilibili

## triggers
- 打开B站
- 打开 B 站
- 打开bilibili
- 打开哔哩哔哩
- B站
- 哔哩哔哩

## description
在默认浏览器中打开 bilibili.com。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://www.bilibili.com", "description": "打开 B 站首页"}
]
```
