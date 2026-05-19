---
name: open-douyin
description: 打开抖音网页版（默认浏览器）
allowed-tools:
  - open_url
---

# open-douyin

## triggers
- 打开抖音
- 抖音
- 看抖音
- 启动抖音

## description
在默认浏览器中打开抖音网页版。

## confirm_required
false

## steps
```json
[
  {
    "tier": "D",
    "action": "open_url",
    "url": "https://www.douyin.com",
    "description": "打开抖音首页"
  }
]
```

## learned
- 抖音网页版反爬较强，长期建议改走客户端 + 快捷键路线
