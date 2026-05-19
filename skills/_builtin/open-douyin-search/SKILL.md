---
name: open-douyin-search
description: 打开抖音搜索特定关键词（演示参数化模板）
argument-hint: '[搜索关键词]'
allowed-tools:
  - open_url
---

# open-douyin-search

## triggers
- 抖音搜
- 抖音搜索
- 在抖音搜
- 抖音找
- 看抖音的

## description
默认浏览器打开抖音搜索页（关键词=用户原话减去触发词部分）。
注：当前 v2.0 还没实现 trigger 参数抽取，命中后会跳到通用搜索；
想要"抖音搜不惑兄弟"精确命中需要 D8 阶段加 argument 抽取。
当前先作为 LLM 学习时的样例参考。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://www.douyin.com/search/", "description": "打开抖音搜索页"}
]
```
