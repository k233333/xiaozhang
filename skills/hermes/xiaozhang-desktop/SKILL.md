---
name: xiaozhang-desktop
description: Windows 桌面控制技能 — 通过 xz.py CLI 操作本机应用、系统、媒体。所有桌面操作都应通过此技能执行。
version: 2.1.0
platforms: [windows]
metadata:
  author: k9211
  tags: [desktop, automation, windows, pyautogui, media, apps]
  category: desktop-automation
---

# XiaoZhang Desktop Control

## When to Use
当用户要求操作本机桌面时使用此技能：打开应用、搜索抖音/B站、系统控制（音量/截图/锁屏）、媒体控制。

**所有桌面操作必须通过 `python xz.py` 执行，禁止直接用 browser/web_search 工具操作本地应用。**

## CLI 接口

工作目录：`D:\11111begin\xiaozhang`
Python：`.venv\Scripts\python.exe`

### 可用命令

| 命令 | 用途 | 示例 |
|---|---|---|
| `douyin-search <关键词>` | 抖音客户端搜索播放 | `python xz.py douyin-search 不惑兄弟` |
| `bilibili-search <关键词>` | B站搜索（Chrome打开） | `python xz.py bilibili-search 原神攻略` |
| `open-app <应用名>` | 打开任意已安装应用 | `python xz.py open-app chrome` |
| `system <操作>` | 系统控制 | `python xz.py system screenshot` |
| `media <操作>` | 媒体播放控制 | `python xz.py media play-pause` |
| `run-turn <文字>` | 完整AI链路（含LLM规划） | `python xz.py run-turn 帮我查天气` |

### system 支持的操作
screenshot / lock / mute / volume-up / volume-down / play-pause / show-desktop

### media 支持的操作
play-pause / next / prev / stop

### open-app 支持的应用名（模糊匹配）
chrome / 微信 / wechat / qq / steam / vscode / 抖音 / edge / 记事本 / 计算器 / 终端 / 资源管理器 / pycharm / word / excel / ppt / 剪映 / obs / 网易云音乐 / telegram / discord

## 输出格式
- 成功：`[OK] 描述`
- 失败：`[FAIL] 原因`（输出到 stderr）
- 未知命令：`[ERROR] 描述`

## Procedure
1. 确定用户意图对应哪个命令
2. 用 terminal 工具执行：`cd D:\11111begin\xiaozhang && .venv\Scripts\python.exe xz.py <命令> <参数>`
3. 检查输出是否包含 `[OK]`
4. 如果失败，尝试 `run-turn` 走完整 AI 链路兜底

## Pitfalls
- 中文参数直接传，不需要 URL 编码
- 抖音搜索需要抖音客户端已安装且窗口存在
- open-app 支持模糊匹配，"微信"和"wechat"都能识别
- run-turn 会调用 LLM，耗时 3-30 秒，简单操作优先用专用命令
