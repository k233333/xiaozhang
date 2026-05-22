---
name: xiaozhang-desktop
description: Windows 桌面控制 + 资源搜索下载 + 资讯抓取。所有本机操作和爬虫任务都通过此技能的 xz.py CLI 执行。
version: 3.0.0
platforms: [windows]
metadata:
  author: k9211
  tags: [desktop, automation, windows, torrent, crawler, news, media, download]
  category: desktop-automation
---

# XiaoZhang Desktop Control + Crawler

## When to Use
- 用户要求操作本机桌面（打开应用、音量、截图等）
- 用户要求搜索/下载影视资源（美剧、电影、动漫）
- 用户要求看科技/金融资讯
- 用户要求播放抖音/B站内容

**所有操作必须通过 xz.py 执行。**

## 执行方式

```
cd D:\11111begin\xiaozhang && .venv\Scripts\python.exe xz.py <命令> <参数>
```

## 全部命令

### 资源搜索与下载

| 命令 | 用途 | 示例 |
|---|---|---|
| `search-torrent <关键词>` | 搜索磁力资源（自动过滤<1080p和死种） | `xz.py search-torrent "White Lotus S03"` |
| `download <磁力链>` | 用迅雷打开磁力链接下载 | `xz.py download "magnet:?xt=urn:btih:..."` |
| `news [话题]` | 抓取科技/金融资讯 | `xz.py news tech` |

#### search-torrent 使用规则
1. 优先用英文名搜索（资源多），中文名可作为补充搜索
2. 输出包含 `[BEST]` 和 `[BEST_MAGNET]` 标记最佳资源
3. **必须先向用户展示搜索结果，等用户确认后再调 download**
4. 向用户展示时说清楚：片名、大小、做种数、来源
5. 如果没找到结果，建议用户换关键词（如加年份、用英文原名）

#### download 使用规则
1. 参数是完整的 magnet: 链接（从 search-torrent 的 [BEST_MAGNET] 获取）
2. 会自动打开迅雷，用户在迅雷里确认下载位置

#### news 话题选项
- `tech` 或 `all` — 全部科技资讯（HackerNews + 36kr）
- `hn` 或 `hackernews` — 英文科技（Hacker News Top Stories）
- `36kr` 或 `国内` — 中文科技创投

### 媒体播放

| 命令 | 用途 | 示例 |
|---|---|---|
| `douyin-search <关键词>` | 抖音客户端搜索播放 | `xz.py douyin-search 不惑兄弟` |
| `bilibili-search <关键词>` | B站搜索（Chrome打开） | `xz.py bilibili-search 原神攻略` |
| `media <操作>` | 媒体播放控制 | `xz.py media play-pause` |

media 操作：play-pause / next / prev / stop

### 应用与系统

| 命令 | 用途 | 示例 |
|---|---|---|
| `open-app <应用名>` | 打开任意已安装应用（模糊匹配） | `xz.py open-app chrome` |
| `system <操作>` | 系统控制 | `xz.py system mute` |

system 操作：screenshot / lock / mute / volume-up / volume-down / show-desktop
open-app 支持：chrome / 微信 / qq / steam / vscode / 抖音 / edge / 记事本 / 计算器 / pycharm / word / excel

### 兜底

| 命令 | 用途 |
|---|---|
| `run-turn <文字>` | 走完整链路（本地skill匹配 → 执行），简单操作优先用专用命令 |

## 输出格式
- `[OK]` — 成功
- `[FAIL]` — 失败（stderr）
- `[BEST]` — 最佳资源标题
- `[BEST_MAGNET]` — 最佳资源磁力链（供 download 命令使用）
- `[HEALTH]` — 种子健康状态

## Procedure

### 用户要找资源时
1. 执行 `search-torrent "<英文名或中文名>"`
2. 解读输出，向用户汇报：找到几个结果、最佳是什么、多大、多少人做种
3. 问用户"要下载吗？"
4. 用户确认后，从输出中取 `[BEST_MAGNET]` 的值，执行 `download "<磁力链>"`
5. 告诉用户"已发送到迅雷"

### 用户要看资讯时
1. 执行 `news tech`（或根据用户指定的话题）
2. 从输出中提取标题列表，用自然语言汇报给用户
3. 如果用户对某条感兴趣，可以用 `open-app chrome` 然后提供链接

### 用户要操作桌面时
1. 判断对应哪个命令
2. 执行
3. 检查 `[OK]` 确认成功

## Pitfalls
- search-torrent 已自动过滤 720p 以下和 0 做种的死种
- 中文片名搜索结果可能少，优先用英文原名
- download 的参数必须是完整的 magnet: 开头的链接
- 迅雷需要已安装且关联了磁力链接协议
- news 需要网络代理（已配置 127.0.0.1:7897）
