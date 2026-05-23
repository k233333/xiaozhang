# 小张项目状态总结（2026-05-23 更新）

> 本文件供下一个对话窗口的 AI 快速理解项目全貌。每次重大进展后更新。

## 一句话概述

Windows 桌面语音助手"小张"，v3.0 架构重构完成。小张进程只负责音频层（唤醒词+录音+ASR+TTS+气泡）+ 资源管理，**Hermes 作为大脑**处理所有 LLM 调用和复杂决策。本地 skill 快速路径（0.3s）+ Hermes 慢速路径（4-8s）混合模式，成功执行后自动学成 skill 下次直接命中。

## 架构（v3.0 — Hermes 作为大脑）

```
小张进程（纯音频层，常驻后台）：
  麦克风 → 唤醒词"小张" → 录音 → ASR → 文字
  → 本地 skill 匹配（命中 → 0.3s 直接执行）
  → 未命中 → Hermes AIAgent.chat()（进程内调用）
  → 返回回复 → TTS 播报 + 气泡
  + 游戏检测 watchdog → 自动卸载/加载音频模型

Hermes（大脑，进程内 Python 库调用）：
  接收文字 → skill 匹配 / LLM 规划 → 调 xz.py 执行
  DeepSeek-Chat API（主力）
  成功后 → 小张自动生成 SKILL.md → 下次本地命中
```

## 项目位置

```
D:\11111begin\xiaozhang\          # 小张主项目
D:\11111begin\hermes-agent\       # Hermes Agent（独立安装）
C:\Users\k9211\.hermes\skills\    # Hermes 的 skill 目录（含小张的 SKILL.md）
```

## GitHub 仓库

https://github.com/k233333/xiaozhang （公开）

## 技术栈

- Python 3.11 + uv 包管理
- LLM：**全部由 Hermes 调用**，小张不再直接调 LLM API
  - DeepSeek-Chat（主力，¥1/M tokens）
  - Groq Llama-70B（fallback，免费但 TPM 限制 12K）
  - Gemini 2.5 Flash（Vision，免费额度）
- ASR：faster-whisper small CPU（1.6s 延迟）
- TTS：edge-tts 晓晓声音（异步非阻塞，自动缓存）
- 本地模型：DirectML GPU（7900 XTX 24GB）
- 桌面自动化：pyautogui + pywinauto
- 记忆：SQLite + FTS5 + ChromaDB
- 爬虫：httpx + Playwright（browser fallback）

## 关键文件

| 文件 | 用途 |
|---|---|
| `main.py` | CLI 入口 + 守护进程 |
| `xz.py` | Hermes↔小张 CLI 桥接（所有桌面操作的入口） |
| `src/runtime.py` | 混合模式路由（本地 skill → Hermes fallback → 自学习） |
| `src/audio/tts.py` | TTS 语音合成（edge-tts） |
| `src/audio/wake_word_custom.py` | 自训练唤醒词检测（sklearn ONNX） |
| `src/crawlers/torrent_search.py` | 磁力资源搜索（PirateBay API） |
| `src/crawlers/pan_search.py` | 夸克网盘搜索（多源聚合） |
| `src/crawlers/news_feed.py` | 科技/金融资讯抓取 |
| `src/core/resource_manager.py` | 游戏感知 + 模型加载/卸载 |
| `src/local_models/wake_word_model.py` | 唤醒词模型加载（修复：用 wake_word_custom 而非 openWakeWord） |
| `startup.ps1` | 开机自启动脚本 |
| `scripts/preload_models.py` | 模型预加载到 GPU |
| `skills/hermes/xiaozhang-desktop/SKILL.md` | 教 Hermes 怎么用 xz.py |
| `skills/hermes/caveman/SKILL.md` | 省 token 的回复风格 |

## xz.py 可用命令

```
douyin-search <关键词>     抖音客户端搜索播放
bilibili-search <关键词>   B站搜索（Chrome打开）
open-app <应用名>          打开应用（模糊匹配）
system <操作>             screenshot/lock/mute/volume-up/volume-down/show-desktop
media <操作>              play-pause/next/prev/stop
search-torrent <关键词>    磁力资源搜索（自动过滤<1080p+死种）
search-pan <关键词>        夸克网盘搜索
download <磁力链>          迅雷下载
news [话题]               科技/金融资讯（tech/36kr/hn）
run-turn <文字>           完整链路（本地skill→Hermes）
```

## 开机自启动

- Windows 计划任务：`XiaoZhang-Hermes-Startup`
- 触发：登录后延迟 2 分钟
- 执行：`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File startup.ps1`
- 工作目录：`D:\11111begin\xiaozhang`
- 耗时：4 秒（模型预加载 2.4s + 启动进程）
- 日志：`logs/startup_*.log`

### 之前启动失败的原因（已修复）
- ExecutionTimeLimit 5分钟超时 → 改为无限制
- PowerShell 5.1 不认 UTF-8 中文 → 改为全英文日志
- `main.py daemon` 子命令不存在 → 改为 `main.py start`
- powershell.exe 没用完整路径 → 改为 `C:\Windows\System32\...`
- 模型加载用 here-string 内嵌 Python → 改为独立 `scripts/preload_models.py`

## Hermes 配置

### 已启用的 toolsets（精简后，省 60% tokens）
- terminal（核心，调 xz.py）
- file（文件操作）
- skills（skill 匹配）
- memory（记忆）

### 已禁用的 toolsets
web, browser, code_execution, vision, image_gen, tts, todo, session_search, clarify, delegation, cronjob, messaging, computer_use

### Token 优化
- 精简 toolsets：system prompt 从 ~20K 降到 ~5-8K tokens
- Caveman skill：输出 tokens 省 65-75%
- 本地 skill 快速路径：命中时 0 token 消耗
- 优化后一次对话 ~6.5K tokens ≈ ¥0.007

### API 状态（2026-05-23）
- DeepSeek：**余额不足（402）**，需要充值 https://platform.deepseek.com/top_up
- Groq：可用但 TPM 限制 12K（Hermes prompt 太大）
- Gemini：免费额度用完（429）

### Hermes 使用统计
- 38 个 session，729 条消息
- 全部是用户自己使用，未被盗用

## 游戏感知资源管理

| 模式 | 加载的模型 | 显存 |
|---|---|---|
| Standard | wake_word + silero_vad + sensevoice + omniparser | ~2GB |
| Gaming | 仅 wake_word（26KB） | 0 |

- 切换触发：进程白名单 / 全屏检测 / GPU>50% / CPU>70%
- 切换延迟：3 秒抖动抑制
- 自学习：未知游戏自动加入白名单

## 本地 Skill 系统

- 50 个 skill（42 builtin + 6 generated + 2 hermes）
- 匹配方式：字面包含 → difflib 模糊 → ChromaDB 向量
- 阈值：字面覆盖率 ≥ 0.7，模糊 ≥ 0.85，向量距离 < 0.35
- 自学习：Hermes 成功执行后自动生成 SKILL.md

## 唤醒词

- 模型：`models/wake_word/xiaozhang_wakeword.onnx`（26KB，sklearn 分类器）
- 准确率：99.8%，阈值 0.7
- 特征：80 维 mel（40 bins × mean+std）
- **注意**：不能用 openWakeWord 的 `Model()` 加载（输出 shape 不兼容），必须用 `wake_word_custom.py` 直接 onnxruntime 推理
- 训练数据：493 个 wav 文件（已在 GitHub）

## 爬虫功能

### 磁力搜索（search-torrent）
- 源：PirateBay API（apibay.org，最稳定）+ 1337x（备用，经常 403）
- 自动过滤：<1080p 排除，0 seeders 排除
- 健康检查：UDP tracker scrape（代理环境下可能不工作）

### 夸克网盘搜索（search-pan）
- 源：quarksoo + miaosou + haisou + Bing site:搜索
- 现状：API 源不太稳定（403/SSL 失败），Bing 兜底打开浏览器
- 后续：Hermes 可以用 browser 工具从搜索结果页提取链接

### 资讯（news）
- HackerNews（JSON API，最稳定）
- 36kr（热榜 API）

## Git 代理配置

```
git config --global http.proxy "http://127.0.0.1:7897"
git config --global https.proxy "http://127.0.0.1:7897"
git config --global http.sslVerify false
```

push 时如果卡住，用 token 方式：
```powershell
$token = (gh auth token); git remote set-url origin "https://${token}@github.com/k233333/xiaozhang.git"; git push; git remote set-url origin "https://github.com/k233333/xiaozhang.git"
```

## 常用命令

```cmd
cd D:\11111begin\xiaozhang

# 小张
.venv\Scripts\python.exe main.py status
.venv\Scripts\python.exe main.py speak "打开抖音"
.venv\Scripts\python.exe xz.py search-torrent "White Lotus S03"
.venv\Scripts\python.exe xz.py search-pan 低智商犯罪
.venv\Scripts\python.exe xz.py news tech

# Hermes
D:\11111begin\hermes-agent\venv\Scripts\hermes.exe chat -q "hello"
D:\11111begin\hermes-agent\venv\Scripts\hermes.exe tools list
D:\11111begin\hermes-agent\venv\Scripts\hermes.exe sessions stats

# 测试
.venv\Scripts\python.exe -m pytest tests/ -q

# Git（需要代理）
C:\Users\k9211\scoop\shims\git.exe push
C:\Users\k9211\scoop\shims\gh.exe auth status
```

## 注意事项（给下一个 AI 看）

1. **uv/git/gh 不在 PATH 里** — 用完整路径 `C:\Users\k9211\scoop\shims\*.exe`
2. **PowerShell 5.1 不认 UTF-8** — 脚本里不要写中文，用英文
3. **代理端口 7897** — 系统代理 `127.0.0.1:7897`，git/gh 需要设环境变量
4. **Hermes 不直接调 LLM** — 小张进程通过 `from run_agent import AIAgent` 进程内调用
5. **wake_word 不能用 openWakeWord Model()** — 必须用 `wake_word_custom.py`
6. **DeepSeek 余额** — 当前欠费，需要充值才能用 Hermes
7. **skill 目录分离** — `skills/_builtin/` 和 `skills/_generated/` 是小张本地用的，`skills/hermes/` 是给 Hermes 看的（需要同步到 `~/.hermes/skills/`）
8. **测试 107 项全过** — 改完代码跑 `pytest tests/ -q` 确认

## 2026-05-23 会话进展

### TTS 语音回复
- 新增 `src/audio/tts.py`：edge-tts 晓晓声音，异步非阻塞，mp3 缓存
- `_h_say` 动作：气泡 + TTS 播报
- main.py 回复：优先用 plan.note，否则默认文字

### 架构重构：Hermes 作为大脑
- `runtime.py` 重写：删除所有直接 LLM 调用
- 混合模式：本地 skill 0.3s → Hermes fallback 4-8s → 自学习闭环
- Hermes 作为 Python 库进程内调用（`from run_agent import AIAgent`）

### 开机自启动修复
- 计划任务 ExecutionTimeLimit 改为无限制
- startup.ps1 全英文重写（避免 PowerShell 5.1 编码问题）
- `main.py daemon` → `main.py start`
- 独立 `scripts/preload_models.py`
- 模型预加载 2.4s 全部 GPU

### wake_word 模型修复
- 根因：xiaozhang_wakeword.onnx 是 sklearn 分类器（1D 输出），不兼容 openWakeWord Model()
- 修复：`wake_word_model.py._load()` 改为调用 `wake_word_custom._load()`
- 验证：Standard 模式 4 个模型全部加载成功，Gaming 模式只保留 wake_word

### 爬虫 skill
- `src/crawlers/torrent_search.py`：PirateBay API + 1337x，自动过滤 <1080p + 死种
- `src/crawlers/pan_search.py`：夸克网盘多源聚合 + Bing 兜底
- `src/crawlers/news_feed.py`：HackerNews + 36kr
- xz.py 新增：search-torrent / search-pan / download / news

### Token 优化
- 禁用 13 个不用的 Hermes toolsets（20K→5-8K tokens/call）
- 安装 Caveman skill（输出省 65-75%）
- 综合省 ~70%

### GitHub 推送
- 仓库：https://github.com/k233333/xiaozhang
- gh CLI 安装 + 认证（device flow）
- git 代理配置（http.proxy + sslVerify=false + token push）

### 模块化调研结论
- **不需要 Python 模块化**（src/modules/ 已删除）
- 正确做法：xz.py 命令 + SKILL.md 描述
- 符合 agentskills.io 开放标准（Anthropic 发起，Claude Code/Hermes/Codex 都支持）

### 待办
1. **DeepSeek 充值** — 当前欠费，Hermes 无法工作
2. **唤醒词实测** — 模型加载成功但从未实际触发过
3. **网盘搜索 API 稳定性** — 当前源经常 403，需要找更稳定的或自建 PanSou
4. **Hermes fallback 配置** — 充值后加 Groq/Gemini 作为备用
5. **browser toolset 按需启用** — 需要爬网页时临时 `hermes tools enable browser`
