---
name: open-weibo
description: 在默认浏览器打开微博
allowed-tools:
  - open_url
---

# open-weibo

## triggers
- 打开微博
- 微博

## description
默认浏览器打开 weibo.com。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://weibo.com", "description": "打开微博"}
]
```
