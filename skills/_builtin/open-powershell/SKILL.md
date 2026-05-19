---
name: open-powershell
description: 打开 PowerShell
allowed-tools:
  - launch_app
---

# open-powershell

## triggers
- 打开PowerShell
- 打开 powershell
- 打开pwsh
- 启动PowerShell
- PowerShell

## description
启动 PowerShell（优先 pwsh，找不到则回落 powershell）。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["pwsh.exe"], "description": "启动 PowerShell 7", "fallback_tier": "D"}
]
```

## learned
- pwsh 装好后通常在 PATH，否则 fallback 用 powershell.exe（系统自带 5.1）
