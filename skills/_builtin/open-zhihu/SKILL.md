---
name: open-zhihu
description: 在默认浏览器打开知乎
allowed-tools:
  - open_url
---

# open-zhihu

## triggers
- 打开知乎
- 知乎

## description
默认浏览器打开 zhihu.com。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://www.zhihu.com", "description": "打开知乎"}
]
```
