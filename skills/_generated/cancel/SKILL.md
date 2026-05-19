# 取消当前操作

## triggers
- 取消
- 别打开
- 误触
- 停止
- 不要

## description
当用户发出紧急取消指令时，发送 Escape 键中断当前操作并口头确认

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "keys", "keys": "escape", "fallback_tier": "D", "timeout_seconds": 1.0, "requires_confirmation": false},
  {"tier": "D", "action": "say", "text": "已取消", "fallback_tier": "D", "timeout_seconds": 1.0, "requires_confirmation": false}
]
```

## learned
- 用户说"慢点发开"实际上是变形的"别打开"，紧急取消应优先使用 Escape 键而非其他复杂方案
- 取消后要立即口头确认，用户才能安心
