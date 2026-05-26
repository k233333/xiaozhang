# 小张项目状态总结（2026-05-24 更新）

> 本文件供下一个对话窗口的 AI 快速理解项目全貌。每次重大进展后更新。

## 一句话概述

Windows 桌面语音助手"小张"，v4.0 CC Brain 版。小张进程负责音频层 + 资源管理 + 视觉感知层，**cc_brain（多 provider LLM 路由）** 作为大脑。三级快速路径：JSON skill（视觉学习，0 token，< 0.5s）→ SKILL.md（手写/自动生成，0 token，0.3s）→ CC Brain LLM（5-15s）。成功执行后自动学成 skill，越用越快。**所有本地模型全部 DirectML GPU，CPU 几乎 0 负载。**

## 架构（v4.0 — CC Brain 多 Provider 路由）

```
小张进程（常驻后台）：
  麦克风 → 唤醒词"小张" → 录音 → ASR → 文字
  → JSON skill 匹配（视觉学习产出，0 token，< 0.5s）
  → SKILL.md 匹配（命中 → 0.3s 直接执行）
  → 未命中 → cc_brain.chat()（OpenAI 兼容 API + tool_use）
  → 返回回复 → TTS 播报 + 气泡
  + 游戏检测 watchdog → 自动卸载/加载音频模型

CC Brain（大脑，src/brain/cc_brain.py）：
  走 llm.yaml 路由，自动 fallback：
    ccb (gpt-5.5, aijh.huanmin.top) → DeepSeek-Chat → Groq Llama-70B
  支持 OpenAI function calling（tool_use 循环）
  LLM 决定调哪个 xz.py 命令 → 本地执行 → 返回结果
  成功后 → 小张自动生成 SKILL.md → 下次本地命中
```

## 项目位置

```
D:\11111begin\xiaozhang\          # 小张主项目（唯一）
```

**已废弃**：Hermes Agent（D:\11111begin\hermes-agent\）不再使用，大脑已切到 cc_brain.py

## GitHub 仓库

https://github.com/k233333/xiaozhang （公开）

## 技术栈

- Python 3.11 + uv 包管理
- LLM：**cc_brain.py 多 Provider 路由**（自动 fallback）
  - ccb / gpt-5.5（aijh.huanmin.top，主力旗舰）— ✅ 可用
  - DeepSeek-Chat（稳定便宜，¥1/M tokens）— ✅ 可用
  - Groq Llama-70B（免费备用，TPM 限制 12K）— ✅ 可用
  - Gemini 2.5 Flash（Vision）— ❌ API key 泄露被封
- ASR：faster-whisper small CPU（1.6s 延迟）
- TTS：edge-tts 晓晓声音（异步非阻塞，自动缓存）
- 本地模型：**全部 DirectML GPU**（7900 XTX 24GB），CPU 0 负载
  - YOLOv8 ONNX（UI 控件检测，78ms）
  - RapidOCR ONNX×3（中英文 OCR，1.2s）
  - SenseVoice ONNX（中文 ASR）
  - Silero VAD ONNX（静音检测）
  - 自训练唤醒词 ONNX（sklearn 分类器）
- 桌面自动化：pyautogui + pywinauto + **Playwright CDP**（Chrome 接管）
- 视觉学习：YOLOv8 + RapidOCR → JSON skill → 0 token 重放
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
1. ~~**DeepSeek 充值**~~ — ✅ 已充值，Hermes 可用
2. **唤醒词实测** — 模型加载成功但从未实际触发过
3. **网盘搜索 API 稳定性** — 当前源经常 403，需要找更稳定的或自建 PanSou
4. **Hermes fallback 配置** — 加 Groq/Gemini 作为备用
5. **browser toolset 按需启用** — 需要爬网页时临时 `hermes tools enable browser`
6. **Phase 3 视觉学习优化** — skill 失效检测（fail_count > 3 → 重新学习）、微信/WeGame pywinauto 补充、多分辨率适配

---

## 2026-05-23 下午会话进展（视觉交互 + 零 Token Skill 化）

### 新增核心能力：视觉学习 + 0 Token 重放

**核心思想**：视觉推理只做一次（学习）→ 编译成 deterministic skill → 永久 0 token 复用

```
第一次：chrome-click "播放" → Playwright 找 selector → 生成 JSON skill（~2s）
第二次：用户说"播放" → JSON skill 命中 → 直接 playwright_click → 0 token，< 0.5s
```

### 新增文件

| 文件 | 用途 |
|---|---|
| `src/actions/raw_input.py` | 底层坐标点击 / 键盘 / 输入（pyautogui 包装） |
| `src/actions/playwright_action.py` | CDP 接管 Chrome，CSS/role/text 选择器点击 + 启发式元素查找 |
| `src/skills/json_skill.py` | JSON skill 存储 / 匹配 / 执行 / 学习 / 防爆 / 清理 |
| `src/vision/screen_parser.py` | 截屏 → YOLOv8 ONNX + RapidOCR → 元素表 → 字符串匹配 |
| `src/local_models/rapidocr_model.py` | RapidOCR 注册为 LocalModel，resource_manager 统一管理 |

### xz.py 新增命令（视觉交互，0 token）

| 命令 | 用途 | 延迟 |
|---|---|---|
| `click-xy <x> <y>` | 坐标点击（最快兜底） | ~10ms |
| `launch-chrome [url]` | 启动/复用 CDP Chrome（9222） | ~1s |
| `playwright-click <选择器>` | CSS/role/text 选择器点击 Chrome 元素 | ~0.5s |
| `chrome-click <描述>` | 自然语言找 Chrome 元素并点击 | ~1s |
| `learn-chrome <描述> -- <t1>\|<t2>` | 学 Chrome 元素 → 生成 JSON skill | ~1s |
| `screen-parse` | 截屏 + YOLO + OCR → 打印元素表 | ~1.4s |
| `find-element <描述>` | OCR 找屏幕元素，输出坐标 | ~1.4s |
| `screen-click <描述> [-- <t1>\|<t2>]` | OCR 找元素并点击；带 -- 时学成 skill | ~1.5s |
| `skill-run <名>` | 直接执行已学的 JSON skill | ~0.5s |
| `skill-list` | 列出所有 JSON skill | 即时 |
| `skill-prune [--dry]` | 清理低质量/久未使用 JSON skill | 即时 |

### 本地模型全部 DirectML GPU（CPU 0 负载）

| 模型 | 用途 | 显存 | 延迟（热启动） |
|---|---|---|---|
| wake_word（sklearn ONNX） | 唤醒词 | ~1MB | <1ms |
| silero_vad | 静音检测 | ~20MB | <1ms |
| sensevoice | 中文 ASR | ~600MB | ~1.6s |
| omniparser（YOLOv8 ONNX） | UI 控件检测 | ~80MB | 78ms |
| rapidocr（PaddleOCR ONNX×3） | 中英文 OCR | ~200MB | 1.2s |

**关键决策**：OCR 从 EasyOCR（PyTorch CPU，28s）换成 RapidOCR（ONNX DirectML，1.2s）。
AMD 7900 XTX 上 PyTorch 走不了 GPU（CUDA 是 NVIDIA），必须用 ONNX + DirectML。

### resource_manager 统一管理

- 开机 → 2 分钟后启动 → 立即加载 wake_word + silero_vad（1.5s）
- 60s 后延迟加载 sensevoice + omniparser + rapidocr（~8s）
- 全部常驻 GPU 显存，后续调用 0 初始化开销
- 游戏模式：卸载所有重模型，只保留 wake_word（显存 0）
- `screen_parser.py` 从 resource_manager 拿已加载 session，不再自己懒加载

### runtime.py 路由变化

```
用户说话 → ASR 文字
  → JSON skill 命中（视觉学习产出，0 token，< 0.5s）  ← 新增
  → SKILL.md 命中（手写/Hermes 生成，0 token，0.3s）
  → Hermes 大脑（4-8s，调 LLM）→ 成功后自动学成 SKILL.md
```

### 防爆机制（避免巨量低质量 skill）

**runtime.py `_try_learn_skill` 6 道闸**：
- A. 操作类（回复含 [OK]/已打开/已执行）
- B. 长度 4-40 字
- C. 24h 冷却 + merge_triggers
- D. 现有 skill 已能命中 → 不学
- E. 黑名单语义（取消/算了/几点/天气/你是谁）
- F. 同 intent slug 走 merge_triggers 而非新建

**json_skill.py 防爆**：
- 同 selector + 同 domain → 合并 trigger 而非新建
- 单 skill trigger ≤ 12
- `prune()`：30 天 use=0 删 / ≥5 次失败率 ≥ 70% 删 / 总数 > 200 LRU 淘汰

**generator.py `merge_triggers`**：
- 对已有 SKILL.md 追加新 trigger（去重，上限 12）

### Hermes SKILL.md 更新

`skills/hermes/xiaozhang-desktop/SKILL.md` 已更新，包含：
- 完整视觉交互命令表
- 使用规则（Chrome 操作优先 chrome-click，本地程序用 screen-click）
- Procedure（网页操作流程 / 本地程序按钮流程）
- 已同步到 `C:\Users\k9211\.hermes\skills\xiaozhang-desktop\SKILL.md`

### 端到端验证（Hermes + DeepSeek API）

| 测试 | Hermes 行为 | 结果 |
|---|---|---|
| "帮我点击B站首页按钮" | run-turn → JSON skill 命中 → playwright 点击 | ✅ |
| "用 chrome-click 点击热门" | launch-chrome → chrome-click 热门 | ✅ |
| "用 screen-click 点击 File" | run-turn → OCR 找到 → 坐标点击 | ✅ |
| "用 learn-chrome 学习动画按钮" | learn-chrome → 生成 JSON skill | ✅ |

### 已学到的 JSON skill

```
skills/_json/首页.json    — B站首页（role=link[name="首页"]），triggers: b站首页|打开b站首页|回到首页
skills/_json/动画.json    — B站动画（text=动画），triggers: b站动画|看动画
```

### pyproject.toml 新增可选依赖

```toml
vision = ["rapidocr-onnxruntime>=1.3", "ultralytics>=8.4"]
```

### 已安装的新依赖（venv 里）
- `rapidocr-onnxruntime`（PaddleOCR ONNX，DirectML OCR）
- `ultralytics`（YOLOv8，仅用于一次性导出 ONNX）
- `onnxslim`（ONNX 模型优化）
- `easyocr`（CPU 兜底，未来可移除）

### 模型文件
- `models/omniparser_v2/icon_detect/model.onnx`（80MB，YOLOv8，从 HuggingFace 下载 + ultralytics 导出）
- `models/omniparser_v2/icon_detect/model.pt`（40MB，原始权重，可删）

### 注意事项（给下一个 AI 看）

9. **JSON skill 目录** — `skills/_json/*.json`，视觉学习产出，runtime 优先匹配
10. **screen_parser 从 resource_manager 拿模型** — 不要自己 `ort.InferenceSession()`，用 `resource_manager.get_model("omniparser")` 和 `resource_manager.get_model("rapidocr")`
11. **RapidOCR 不需要 model_path** — 它自带内置 PaddleOCR 模型，`runtime.yaml` 里的 `model_path: models/rapidocr_placeholder` 只是占位
12. **CDP Chrome 端口 9222** — `launch-chrome` 会起一个独立 profile 的 Chrome（`~/.xiaozhang/chrome-profile`），不影响用户日常 Chrome
13. **OCR 4K 屏自动缩放** — `screen_parser._ocr_run` 会把 >1920px 的图缩到 1920 再 OCR，bbox 自动还原回原尺寸
14. **防爆是硬约束** — 不要绕过 `_try_learn_skill` 的 6 道闸，否则会产生巨量低质量 skill

---

## 2026-05-24 会话进展（Hermes → CC Brain 切换完成）

### 大脑切换：Hermes → cc_brain.py（多 Provider 路由）

**根因**：Hermes 作为大脑有以下问题：
- 框架开销大（每次 ~7K tokens system prompt）
- 依赖独立进程/venv，维护成本高
- session history 累积导致 token 爆炸

**新方案 cc_brain.py**：
- 直接调 OpenAI 兼容 API（function calling / tool_use）
- 走 `config/llm.yaml` 路由，自动 fallback 多 provider
- system prompt = soul.md + ccb_system_prompt.md + 用户画像 + 最近记忆
- 每次独立调用，不累积 history
- 支持 tool_use 循环（LLM 决定调 xz.py → 执行 → 返回结果 → LLM 总结）

### Provider 优先级（自动 fallback）

| 优先级 | Provider | 模型 | 状态 |
|---|---|---|---|
| 1 | ccb (aijh.huanmin.top) | gpt-5.5 | ✅ 可用 |
| 2 | DeepSeek | deepseek-chat | ✅ 可用 |
| 3 | Groq | llama-3.3-70b | ✅ 可用 |

### 修复的问题

1. **"不认识小张"** — cc_brain.py 现在加载 soul.md + 用户画像 + 最近记忆到 system prompt
2. **API 硬编码** — 从硬编码 ikuuu 改为走 llm.yaml 路由，任何 provider 挂了自动切下一个
3. **常驻语音没跑** — 电脑重启后 watchdog 进程没启动（计划任务可能没触发）

### 端到端验证（CC Brain + gpt-5.5）

| 测试 | 行为 | 结果 |
|---|---|---|
| "你是谁" | 直接回复身份（不调命令） | ✅ "我是小张，你的桌面语音助手" |
| "我想看不惑兄弟" | 本地 skill 字面命中 → 打开抖音 | ✅ 0 token，6.7s |
| "我想看不惑兄弟"（CC路径） | CC 调用 douyin-search | ✅ gpt-5.5 正确决策 |

### 关键文件变更

| 文件 | 变更 |
|---|---|
| `src/brain/cc_brain.py` | 重写：走 llm.yaml 路由 + OpenAI function calling + 多 provider fallback |
| `config/ccb_system_prompt.md` | 精简：只保留命令表和规则（身份由 soul.md 提供） |

### 当前已知问题

1. **cc/ccb CLI 工具超时** — 这是 cc/ccb 自己的网络问题，跟小张项目无关。小张的 cc_brain.py 直接调 API 是通的
2. **Gemini API key 泄露** — 被 Google 封了（403），需要重新申请。影响：A 级 Vision 兜底不可用
3. **open-chrome skill 执行失败** — `chrome.exe` 不在 PATH，D 级 FileNotFoundError → 降级到 A 级 → Vision 不可用。需要修 skill 的 cmd 为完整路径
4. **常驻语音需要手动启动** — 计划任务可能没触发，需要检查 Task Scheduler

### 注意事项（给下一个 AI 看）

15. **不再用 Hermes** — 大脑已切到 `src/brain/cc_brain.py`，Hermes 相关代码可以忽略
16. **cc_brain 走 llm.yaml** — 不要硬编码 API endpoint，所有 provider 配置在 `config/llm.yaml`
17. **cc/ccb CLI ≠ 小张大脑** — cc/ccb 是用户自己用的终端工具，小张的大脑是 cc_brain.py 直接调 API
18. **tool_use 格式** — 用 OpenAI function calling 格式（不是 Anthropic tool_use），因为 DeepSeek/ccb/Groq 都兼容 OpenAI

---

## 2026-05-26 封档说明

### 项目状态：暂停开发，代码封档

**原因**：token 消耗过大（主要来自 Hermes/cc/ccb CLI 工具，非小张本身），系统调用混乱，决定暂停。

### 已完成的清理

- ✅ 停止所有后台进程（守护进程 / watchdog / cpu_guard）
- ✅ 删除 Windows 计划任务 `XiaoZhang-Hermes-Startup`（不再开机自启）
- ✅ 代码推送 GitHub 封档

### 恢复项目时需要做的事

1. `uv sync` — 重建 venv
2. `.venv\Scripts\python.exe main.py memory init` — 初始化记忆库
3. `.venv\Scripts\python.exe main.py start` — 启动守护进程
4. 如需开机自启：重新创建 Windows 计划任务（参考 startup.ps1）

### 小张本身的 token 消耗（实测）

- 每次 LLM 调用：~1700 input + 35 output tokens ≈ ¥0.001
- 本地 skill 命中：0 token
- 项目总消耗（截至封档）：11,265 tokens ≈ ¥0.01

**2800万 tokens 来自 Hermes/cc/ccb CLI 工具，与小张项目无关。**
