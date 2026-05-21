# 搜索B站并播放第一个视频

## triggers
- 打开chrome搜索bilibili
- 在B站搜索播放视频
- 打开B站搜索并播放第一个视频
- search bilibili play first video

## description
在Chrome中打开B站，搜索指定关键词，自动点击并播放搜索结果中的第一个视频

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "run_cmd", "cmd": ["cmd", "/c", "start", "chrome", "https://search.bilibili.com/all?keyword=<搜索关键词>"], "fallback_tier": "C", "timeout_seconds": 10.0, "requires_confirmation": false},
  {"tier": "D", "action": "wait", "fallback_tier": "D", "timeout_seconds": 4.0, "requires_confirmation": false},
  {"tier": "A", "action": "screenshot_and_decide", "description": "查看搜索结果页面，点击第一个视频进行播放", "fallback_tier": "A", "timeout_seconds": 10.0, "requires_confirmation": false}
]
```

## learned
- B站搜索URL格式固定：https://search.bilibili.com/all?keyword=<关键词>，中文可直接放入URL无需编码
- 搜索页加载后，第一个视频在页面顶部，截图定位准确
- 无需先打开空白Chrome再导航，直接打开搜索URL更高效
