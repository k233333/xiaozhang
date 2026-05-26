# 屏幕文字点击
## triggers
- 在屏幕上找到 File 文字并点击
- 找到 File 并点击
- 点击 File 文字

## description
在屏幕中定位并点击指定文字

## confirm_required
false

## steps
```json
[{"tier":"D","action":"run_cmd","description":"","cmd":["python","xz.py","run-turn","在屏幕上找到File文字并点击它"],"timeout_seconds":10.0,"requires_confirmation":false}]
```

## learned
- 屏幕文字点击任务统一用 Hermes 执行
