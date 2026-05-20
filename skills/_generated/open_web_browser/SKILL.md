# 打开默认浏览器

## triggers
- 打开网页
- 启动浏览器
- 开启浏览器

## description
打开系统默认浏览器并确认其正常启动

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "launch_app", "description": "打开默认浏览器", "cmd": ["cmd", "/c", "start", ""], "fallback_tier": "C", "timeout_seconds": 5.0, "requires_confirmation": false},
  {"tier": "D", "action": "wait", "description": "等待浏览器加载", "timeout_seconds": 3.0, "requires_confirmation": false},
  {"tier": "A", "action": "screenshot_and_decide", "description": "确认浏览器已打开，如有需要打开新标签页", "fallback_tier": "A", "timeout_seconds": 5.0, "requires_confirmation": false}
]
```

## learned
- 使用 `start ""` 而非指定浏览器路径，更通用且兼容不同默认浏览器
- 3秒等待后截图确认状态，避免在浏览器未完全加载时误判断
