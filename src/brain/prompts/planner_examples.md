## 平台操作路径参考

抖音客户端：launch_app→wait 4s→keys "escape"→wait 1s→screenshot_and_decide→type→keys "enter"→wait 3s→screenshot_and_decide
B站网页：open_url "https://search.bilibili.com/all?keyword=X"→wait 3s→screenshot_and_decide
通用搜索：open_url→wait 3s→screenshot_and_decide

## 例子

用户："打开抖音搜不惑兄弟最新视频"
{"intent":"watch_douyin_search","skill_hit":false,"confirm_required":false,"note":"正在搜索","steps":[{"tier":"D","action":"open_url","url":"https://www.douyin.com/search/不惑兄弟","fallback_tier":"C"},{"tier":"D","action":"wait","timeout_seconds":3},{"tier":"A","action":"screenshot_and_decide","description":"点击第一个视频"}]}

## 意图模糊时

{"intent":"ambiguous","skill_hit":false,"confirm_required":false,"note":"你想打开哪个平台？","steps":[]}

## 多步原则

- "搜X"→打开+等加载+点结果
- "播放"→最终步必须点视频
- 不确定UI→screenshot_and_decide
