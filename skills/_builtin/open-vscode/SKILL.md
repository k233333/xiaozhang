---
name: open-vscode
description: 打开 VS Code
allowed-tools:
  - launch_app
---

# open-vscode

## triggers
- 打开VS Code
- 打开 VSCode
- 打开vscode
- 启动VSCode
- VSCode
- VS Code

## description
通过 PATH 中的 code 命令启动 Visual Studio Code。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["code"], "description": "启动 VS Code", "fallback_tier": "C"}
]
```
