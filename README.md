# 小张（XiaoZhang）— Windows 桌面语音助手

> 一句话：**打游戏时是隐形的，不打游戏时是丝滑的，越用越懂你的桌面贾维斯。**

常驻 Windows 后台、纯终端运行的桌面级语音助手。USB 麦克风 → SenseVoice 中文 ASR → DeepSeek（云端 API）规划 → 三级降级桌面自动化执行。具备 Skills 自动生成 + 三层 Memory + 游戏感知动态资源管理。

---

## 目录
1. [快速开始](#快速开始)
2. [日常使用](#日常使用)
3. [架构概览](#架构概览)
4. [配置](#配置)
5. [自学习机制](#自学习机制)
6. [游戏感知](#游戏感知)
7. [开发](#开发)
8. [常见问题](#常见问题)

---

## 快速开始

### 1. 一次性配置

```cmd
copy .env.example .env
notepad .env
```
填入 `DEEPSEEK_API_KEY=sk-xxx`（如果你已经在用 Claude Code 接 DeepSeek，直接复用同一个 key）。

```cmd
uv sync
```
安装 170 个依赖（约 2 分钟）。如有 AMD GPU 想加速本地模型：

```cmd
uv sync --extra gpu --extra sensevoice
```

### 2. 测一句

```cmd
uv run python main.py speak "打开抖音"
```

应该看到：浏览器开了抖音 + 终端打印命中 skill。耗时 0.2 秒左右。

```cmd
uv run python main.py speak "打开记事本"
```

第一次说会调用 LLM 规划（3-6 秒），执行成功后自动产出 SKILL.md。
**第二次同样的话会直接命中刚学的 skill，不再调 LLM。**

---

## 日常使用

### 命令分组

```
xiaozhang [顶层]
├── start                     常驻守护进程（含游戏检测 + cpu_guard）
├── console                   开发期 REPL（键盘代麦克风）
├── speak <text>              一次性测试一句话
├── status                    资源状态：模式 / 模型 / CPU / 内存
└── mode <target>             手动切 standard / gaming / auto

xiaozhang audio
└── list                      列出输入设备

xiaozhang memory
├── init                      初始化记忆库
├── recent [--limit N]        看最近的会话历史
└── search <query>            全文搜索事件流（中英文）

xiaozhang skills
├── list                      列出所有 skill（30+ 内置）
├── stats                     看每个 skill 调用成功率
├── show <name>               看 SKILL.md 完整内容（支持模糊匹配）
├── delete <name>             删 LLM 学的 skill（_builtin 受保护）
└── evolve                    重写低成功率 skill 的 trigger
```

### 常用速查

| 想做什么 | 怎么说（语音）/ 怎么打（CLI）|
|---|---|
| 用键盘测试一条命令 | `uv run python main.py speak "打开计算器"` |
| 后台启动小张 | `uv run python main.py start` |
| 看小张已经会什么 | `uv run python main.py skills list` |
| 看小张学了什么 | `uv run python main.py memory recent` |
| 临时强制省资源 | `uv run python main.py mode gaming` |
| 查看资源占用 | `uv run python main.py status` |
| 帮我看小张是怎么做"打开抖音"的 | `uv run python main.py skills show open-douyin` |
| 我教错了一个 skill 想删 | `uv run python main.py skills delete <name>` |

### 内置 skill 速查（30+，部分）

**开应用**
- 打开抖音 / B 站 / YouTube / GitHub / 知乎 / 微博
- 打开微信 / QQ / Telegram
- 打开 Chrome / Edge
- 打开计算器 / 记事本 / 命令行 / cmd / PowerShell / VS Code / Kiro
- 打开任务管理器 / 资源管理器 / 我的电脑
- 打开 Windows 设置

**系统控制**
- 锁屏 / 离开 / 我去开会
- 静音 / 取消静音
- 音量+ / 音量-
- 上一首 / 下一首
- 暂停 / 播放 / 暂停音乐
- 显示桌面 / 截图

任何不在列表里的指令，第一次说时由 LLM 现规划，**成功后自动学成新 skill，下次直接复用**。

---

## 架构概览

```
USB 麦克风
   ↓ sounddevice
[recorder.py] 录音 + Silero VAD 自动断句
   ↓ AudioChunk
[stt.py] SenseVoice（DirectML 加速）→ 文本
   ↓ 用户原话
[runtime.py] 三段路由
   ↓
   ├─ 1. Skills 字面/模糊匹配 → 命中 → 直接执行（0 LLM 调用，0.5s）
   ├─ 2. Memory 召回 → 复用历史 plan
   └─ 3. LLM 现规划（DeepSeek-Chat 1-3s / Reasoner 8-30s 兜底）
        ↓
        生成结构化 Plan JSON
        ↓
[executor.py] 三级降级执行
   ├─ D 级：URI Scheme / 快捷键 / 命令行（10ms，0 成本）
   ├─ C 级：UIAutomation 控件树 / Playwright DOM（100-500ms）
   └─ A 级：OmniParser → LLM 视觉决策（800ms-2s）
        ↓
   成功 → workflow_recorder 自动产出 SKILL.md
```

后台同时运行三个守护协程：
- `state_machine` — IDLE → ARMED → LISTENING → EXECUTING
- `resource_manager.watchdog` — 5 秒 / 次轮询，按当前模式加载/卸载本地模型
- `cpu_guard` — 5 秒 / 次采样，CPU 持续过载自动切游戏模式让位

---

## 配置

### `config/runtime.yaml`

运行时配置：音频、唤醒词、VAD、资源管理、游戏白名单、本地模型路径、skills、memory、actions。

关键字段：
```yaml
wake_word:
  enabled: false          # D7 阶段才打开（要先训练"小张"模型）
  primary: 小张
  primary_threshold: 0.6

resource_manager:
  watchdog_interval: 5    # 检测间隔
  switch_delay: 3         # 抖动抑制
  thresholds:
    gpu_busy_percent: 50  # GPU > 50% 持续 10s 切游戏
    cpu_busy_percent: 70  # CPU > 70% 持续 30s 切游戏

mode_models:
  standard: [wake_word, silero_vad, sensevoice, omniparser]
  gaming:   [wake_word]   # 游戏模式只保留唤醒词
```

### `config/llm.yaml`

LLM provider + 路由：
```yaml
providers:
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1
    sdk: openai
    models:
      v4: deepseek-chat        # 快，1-3 秒
      v4-pro: deepseek-reasoner # 慢但能想，8-30 秒

routing:
  task_planning:
    primary: deepseek.v4       # 先用 chat（快）
    fallback: deepseek.v4-pro  # chat 不行再上 reasoner
```

加新 provider（Claude / Gemini / Qwen）只需解开 yaml 注释 + 填 env，**代码 0 改动**。

### `config/soul.md`

小张的人设（参考 Friday 项目）。所有 system prompt 都会自动拼接 SOUL.md。改这里能改小张的语气、性格、约束。

---

## 自学习机制

### 三层数据演进

```
 ┌───────────────────────────────────────────────────┐
 │ 第一次说 "打开微博"                                  │
 │   ↓ skills 没命中                                    │
 │   LLM 规划 → Plan{open_url: weibo.com}             │
 │   ↓ 执行成功                                        │
 │   workflow_recorder 自动调 LLM 写 SKILL.md          │
 │   写到 skills/_generated/open_weibo/SKILL.md       │
 │   knowledge-runtime.json → always_skill_match 索引│
 │ 第二次说 "打开微博"                                  │
 │   ↓ skills 字面命中（跳过 LLM）                      │
 │   直接执行 → 0.5 秒完成                             │
 └───────────────────────────────────────────────────┘
```

### Skill 进化（GEPA 启发）

`skills evolve` 命令会：
1. 找出成功率 < 50% 且调用 ≥ 5 次的 skill
2. 把它的 trigger + 最近失败的用户原话喂给 LLM
3. 让 LLM 重写 trigger（备份原文件）

下一次类似的话就更容易命中。

---

## 游戏感知

### 切换条件（任一命中即切游戏模式）

1. **进程白名单**（最快）— 50 个常见游戏（CoD / 英雄联盟 / 原神 / 鸣潮等）
2. **独占全屏**（D3D 全屏几乎 100% 是游戏）
3. **GPU > 50% 持续 10 秒**
4. **CPU > 70% 持续 30 秒**（也兼做高负载保护）
5. **用户手动**：`xiaozhang mode gaming`（最高优先级）

### 黑名单

OBS / DaVinci Resolve / Premiere / HandBrake 等**永远不会被误判为游戏**（直播/视频编辑软件经常吃 GPU 全屏）。

### 自学习白名单

当条件 2 或 3 触发但白名单没命中时，自动把当前进程加入 `auto_learned_games`。**用户 0 维护成本**。

### 模式资源对比

|  | 标准模式 | 游戏模式 |
|---|---|---|
| 加载的本地模型 | wake_word + vad + sensevoice + omniparser | 仅 wake_word |
| 内存占用 | ~1.5GB | ~70MB |
| 显存占用 | ~2GB | 0 |
| CPU 待机 | 1-2% | <1% |
| 端到端延迟 | 1-2s | 3-4s（云端） |
| 游戏帧数影响 | n/a | **0 影响** |

---

## 开发

### 项目结构

```
xiaozhang/
├── main.py                          CLI 入口
├── dev_console.py                   开发 REPL
├── pyproject.toml                   uv 项目配置
├── config/
│   ├── runtime.yaml                 运行时配置
│   ├── llm.yaml                     LLM provider + 路由
│   └── soul.md                      人设
├── src/
│   ├── audio/                       唤醒词 / VAD / 录音 / STT
│   ├── brain/                       LLMRouter + prompts + action_schema
│   ├── memory/                      SQLite + ChromaDB + USER.md
│   ├── skills/                      loader + matcher + generator + parser
│   ├── vision/                      screenshot + OmniParser + vision LLM
│   ├── actions/                     executor + tier_d/c/a
│   ├── tray/                        系统托盘
│   ├── core/                        config / logger / state_machine /
│   │                                game_detector / resource_manager / cpu_guard
│   └── local_models/                4 个本地 ONNX 模型封装
├── skills/_builtin/                 30+ 内置 skill
├── skills/_generated/               LLM 自动学到的 skill
├── data/                            memory.db / USER.md / chroma/
├── models/                          ONNX 模型文件
├── logs/
└── tests/                           pytest 测试套件（99 个测试）
```

### 跑测试

```cmd
uv run pytest tests/ -v               全部
uv run pytest tests/test_config.py    单文件
uv run pytest -k "match" -v           按关键词
```

### 加新 skill

最简单：在 `skills/_builtin/` 下建目录写 SKILL.md 即可，重启自动加载。

模板：
```markdown
---
name: my-skill
description: 一句话描述
allowed-tools:
  - launch_app
---

# my-skill

## triggers
- 触发词1
- 触发词2

## description
做什么

## confirm_required
false

## steps
\`\`\`json
[
  {"tier": "D", "action": "launch_app", "cmd": ["myapp.exe"]}
]
\`\`\`
```

### 加新 LLM provider

1. 在 `config/llm.yaml` 的 `providers:` 加一个：
   ```yaml
   qwen:
     api_key_env: DASHSCOPE_API_KEY
     base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
     sdk: openai
     models:
       max: qwen-max
   ```
2. 改 `routing:` 的某个 task 用它：
   ```yaml
   vision_analysis:
     primary: qwen.max
   ```
3. `.env` 加 `DASHSCOPE_API_KEY=...`
4. **完事**，代码 0 改动。

### 日志

`logs/xiaozhang.log` — 结构化 JSON 日志，每条带 trace_id 便于追踪一次完整交互。

`logs/screenshots/` — 每步操作前的截图归档（可在 .gitignore 关）。

---

## 常见问题

### Q: 第一次说一句话很慢（5-10 秒）？
A: 第一次走 LLM 规划。第二次同样的话会命中 skill，<1 秒完成。日常 80%+ 高频指令一段时间后都是亚秒级。

### Q: 我用的 DeepSeek，为什么有 OpenAI 依赖？
A: DeepSeek 提供 OpenAI 兼容协议端点，用 `openai` SDK + 自定义 `base_url` 即可。`anthropic` SDK 留着备用，未来加 Claude 时不用改代码。

### Q: AMD 显卡能用 GPU 加速吗？
A: 能。`uv sync --extra gpu` 装 `onnxruntime-directml`。微软 + AMD 联合优化，比 ROCm 稳。

### Q: 唤醒词"小张"什么时候能用？
A: D7 阶段。需要自录 30-50 段"小张" + 30 段"你好" 用 openWakeWord 训练 ONNX。当前 `wake_word.enabled=false`，跑 `start` 是键盘 push-to-talk 模式（按回车开始说话）。

### Q: 游戏模式真的不影响帧数吗？
A: 卸载所有非必要本地模型后，进程仅剩 wake_word（CPU < 1%，无 GPU 占用）。从渲染管线角度看几乎隐形。

### Q: 怎么彻底卸载？
A: 删整个 `D:\11111begin\xiaozhang\` 文件夹即可，所有数据都在项目内（`.venv` 在 `.venv/`，记忆在 `data/`）。

### Q: 我教错了一个 skill 想反悔？
A: `uv run python main.py skills delete <name>`，仅 `_generated` 下的可以删，`_builtin` 受保护。

### Q: API 出错怎么办？
A: LLMRouter 自带 retry（默认 2 次） + fallback 路由。两层都失败时返回 None，run_turn 会优雅降级到"没听清"提示。

---

## 致谢

- Skills/Memory 设计受 [Hermes Agent (NousResearch, MIT)](https://github.com/NousResearch/hermes-agent) 启发
- 三层 Memory + Workflow Recorder 思路来自 [Friday by Ascension-Yugi](https://github.com/Ascension-Yugi/Ascension)
- 工程范式继承自 [`D:\11111begin\ttxx1\CClear`](D:/11111begin/ttxx1/CClear)
- 中文 ASR 主力：[FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)
- 屏幕解析：[microsoft/OmniParser](https://github.com/microsoft/OmniParser)
- 唤醒词：[dscripka/openWakeWord](https://github.com/dscripka/openWakeWord)

## 许可

MIT — 自由使用、修改、分发。
