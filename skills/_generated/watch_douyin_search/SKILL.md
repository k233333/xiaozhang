# 搜索抖音博主并播放最新视频

## triggers
- 打开抖音搜<博主名>播放最新视频
- 抖音搜索<博主名>最新视频
- 在抖音找<博主名>的最新视频播放

## description
在抖音搜索指定博主，并自动播放该博主的最新视频

## confirm_required
false

## steps
```json
[
  {
    "tier": "D",
    "action": "open_url",
    "url": "https://www.douyin.com/search/{QUERY}",
    "description": "打开抖音搜索页搜索博主名称",
    "timeout_seconds": 10.0,
    "requires_confirmation": false
  },
  {
    "tier": "D",
    "action": "wait",
    "description": "等待搜索结果加载完成",
    "timeout_seconds": 3.0,
    "requires_confirmation": false
  },
  {
    "tier": "A",
    "action": "screenshot_and_decide",
    "description": "查看屏幕，找到该博主的第一个视频并点击播放",
    "timeout_seconds": 10.0,
    "requires_confirmation": false
  }
]
```

## learned
- 使用`{QUERY}`占位符替换具体博主名，URL结构为`https://www.douyin.com/search/{QUERY}`
- 搜索页加载后需要等待至少3秒让视频列表渲染完成
- 由于抖音页面结构不固定，需要视觉识别来决定点击哪个元素
