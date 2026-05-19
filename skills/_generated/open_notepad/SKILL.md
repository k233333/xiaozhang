# 启动记事本

## triggers
- 打开记事本
- 启动记事本
- 运行记事本

## description
启动 Windows 记事本应用程序

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["notepad.exe"], "timeout_seconds": 10.0, "fallback_tier": "C"}
]
```

## learned
- 记事本的标准系统命令是 notepad.exe，无需管理员权限
- D 层级直接启动即可，失败时走 C 层级模拟 Win+R → notepad → Enter
