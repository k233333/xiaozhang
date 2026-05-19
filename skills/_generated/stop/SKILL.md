# 停止当前操作

## triggers
- 停一下
- 先别上了
- 错了 停
- 取消

## description
当用户要求停止当前正在执行的操作时，立即中断并告知用户。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "say", "description": "告知用户已停止", "text": "好的，已停止。", "timeout_seconds": 10.0, "requires_confirmation": false}
]
```

## learned
- 用户说"停"或"取消"时应立即执行此 skill，无需二次确认
- 此 skill 不依赖任何先决条件
