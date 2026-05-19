---
name: open-obsidian
description: 打开 Obsidian
allowed-tools:
  - launch_app
---

# open-obsidian

## triggers
- 打开Obsidian
- 打开 obsidian
- Obsidian
- 笔记

## description
通过 obsidian:// 协议唤起 Obsidian。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "url": "obsidian://open", "description": "唤起 Obsidian", "fallback_tier": "C"}
]
```
