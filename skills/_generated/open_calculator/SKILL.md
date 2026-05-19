# 打开计算器

## triggers
- 打开计算器
- 启动计算器
- 运行计算器
- 开启计算器

## description
通过系统命令启动Windows内置计算器应用

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "cmd": ["cmd", "/c", "start", "calc"], "fallback_tier": "C", "timeout_seconds": 5.0, "requires_confirmation": false}
]
```

## learned
- Windows自带calc命令可直接启动计算器，无需完整路径
