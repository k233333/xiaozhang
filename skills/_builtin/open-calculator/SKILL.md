---
name: open-calculator
description: 打开 Windows 计算器
allowed-tools:
  - launch_app
---

# open-calculator

## triggers
- 打开计算器
- 启动计算器
- 计算器

## description
启动 Windows 计算器（calc.exe，UWP 版会自动跳转）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["calc.exe"], "description": "启动计算器"}
]
```
