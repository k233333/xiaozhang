# 小张项目状态总结（2026-05-19）

> 本文件供下一个对话窗口的 AI 快速理解项目全貌。每次重大进展后更新。

## 一句话概述

Windows 桌面语音助手"小张"，v2.0 骨架已完工，核心链路（语音→转写→规划→执行→自学习）已跑通验证。修复了 skill 匹配器的向量阈值 bug（之前任意输入都匹配 cancel），唤醒词循环已加入调试日志，待用户实测验证。

## 项目位置

```
D:\11111begin\xiaozhang\
```

## 技术栈

- Python 3.11 + uv 包管理
- LLM：DeepSeek-Chat（主力 0.8s）+ DeepSeek-Reasoner（复杂任务 28s）+ Groq Llama-70B（fallback）+ Gemini 2.5 Flash（Vision）
- ASR：faster-whisper small CPU（当前主力，1.6s 延迟）；SenseVoice 894MB ONNX 已下载到 GPU 但推理管线未对接
- 本地模型：全部走 DirectML（7900 XTX 24GB 显存）
- 桌面自动化：pyautogui + pywinauto + Playwright（已装）
- 记忆：SQLite + FTS5 + ChromaDB 向量召回
- 配置：config/runtime.yaml + config/llm.yaml + config/soul.md

## 已完成 ✅

| 模块 | 状态 | 关键文件 |
|---|---|---|
| LLMRouter 多 provider 三档路由 | ✅ 实测通过 | src/brain/llm_router.py |
| 意图分类器（纯规则 0ms） | ✅ | src/brain/intent_classifier.py |
| 三级降级执行 D/C/A | ✅ | src/actions/executor.py |
| 42 个 builtin skill | ✅ | skills/_builtin/ |
| Skill 自动生成 + 进化 | ✅ 实测"打开记事本"自动学成 skill | src/skills/ + src/learning/ |
| 三层 Memory（SQLite+FTS5+ChromaDB） | ✅ | src/memory/ |
| 游戏感知 + 资源管理 | ✅ | src/core/game_detector.py + resource_manager.py |
| CPU 高负载守护 | ✅ | src/core/cpu_guard.py |
| 冷启动优化（1.9s 响应 + 60s 延迟加载） | ✅ | resource_manager.py |
| DirectML GPU 加速 | ✅ 4 个模型全上 GPU | src/local_models/ |
| Vision（Gemini 2.5 Flash） | ✅ 实测能看屏幕 | src/vision/vision_query.py |
| 系统托盘 | ✅ | src/tray/ |
| CLI 子命令分组 | ✅ | main.py（status/mode/audio/memory/skills/vision/models）|
| 107 个 pytest 测试 | ✅ | tests/ |
| README 用户手册 | ✅ | README.md |
| bench_llm 基准脚本 | ✅ | bench_llm.py |
| 开机自启动脚本 | ✅ | scripts/ |
| 本机软件路径映射 | ✅ | config/apps.yaml |
| 语音录音 + 转写 | ✅ 实测"小张小张"转写正确 | src/audio/recorder.py + stt.py |
| 声音反馈（叮/嘟） | ✅ winsound | recorder.py |
| 抖音客户端搜索播放 | ✅ pyautogui 确定性操作 | src/actions/douyin_actions.py |
| Workflow 录制回放 | ✅ | src/learning/workflow_replay.py |

## 未完成 / 有问题 ❌

| 问题 | 现状 | 下一步建议 |
|---|---|---|
| **唤醒词"小张"** | 自训练 ONNX 分类器 99.8% 准确率，已接入主循环。加入调试日志（静音块统计/能量触发/分类器结果） | 需要实测验证（你说"小张"看能不能触发）。如无声，先看日志里 RMS 值，确认麦克风音频确实进来了 |
| **VAD 误触发 / skill 匹配错误** | 已解决 — 唤醒词启用后只有"小张"命中才开始录音。修复 matcher.py 向量距离阈值 `< 1.0` → `< 0.35`（之前任意输入都匹配 cancel skill）| — |
| **SenseVoice 推理管线** | 894MB ONNX 已下载到 GPU，但 sherpa-onnx 版的输入格式（mel+tokenizer）没对接 | 需要研究 sherpa-onnx 的 SenseVoice 推理 API，或等 funasr 装好 torch |
| **OmniParser 真实推理** | HuggingFace 上是 safetensors 不是 ONNX，icon_detect 404 | 需要从 PyTorch 转 ONNX，或等微软发布官方 ONNX |
| **Vision 坐标不准** | Gemini 在 4K 屏上返回的坐标偏移，点不到目标 | 已改用 pyautogui 确定性坐标；Vision 仅作最后兜底 |
| **recorder.py 旧版残留** | 硬盘上的文件多次重写但有些旧引用可能残留 | 已修了 silence_timeout_ms 和 vad_aggressiveness，基本可用 |

## 关键实测数据

| 场景 | 耗时 | 备注 |
|---|---|---|
| builtin skill 命中（如"打开抖音"） | 0.3s | 0 LLM 调用 |
| 简单任务 LLM 规划（如"打开记事本"） | 3-4s | DeepSeek-Chat |
| 复杂任务 LLM 规划 | 28-32s | DeepSeek-Reasoner（自动 escalate）|
| 语音转写 | 1.6s | faster-whisper small CPU |
| 抖音搜索播放完整链路 | ~12s | pyautogui 确定性操作 |
| 冷启动到可响应 | 1.9s | 轻量模型先加载 |

## API Keys（在 .env 文件中）

- `DEEPSEEK_API_KEY` — 主力 LLM（Chat + Reasoner）
- `GROQ_API_KEY` — Groq Llama-70B fallback
- `GEMINI_API_KEY` — Gemini 2.5 Flash（Vision）

## Git 历史（16 个 commit）

```
0c0a5b1 feat: 语音链路跑通 — 持续监听 + 叮/嘟声音反馈 + faster-whisper 转写
ebdd375 feat: 抖音搜索播放完整链路验证通过 + apps.yaml 软件映射
b79c0d1 wip: 抖音客户端搜索播放链路调试中
fc5e0c1 feat: 扫描本机软件 + apps.yaml 路径映射 + 抖音改走客户端
e4d0858 fix: 多步规划+Vision点击完整链路跑通 + 修3个bug
7d80a7a feat: 修 stt.py + 开机自启动脚本 + ChromaDB 向量召回
7e416ac perf: 冷启动优化 — 立即加载轻量模型，60s 后延迟加载重模型
d567899 fix: 所有本地模型配置改为 directml 优先 + wake_word 模型下载就位
bcc159c feat: 12 个新 builtin skill + workflow 录制回放 + SenseVoice 修复尝试
81716eb feat: M+N — DirectML GPU 加速 + 轻量意图分类器
22ef59e feat: H 选项 + 三档智能路由（task_planning + complex escalate）
de58ea3 docs: session_log 追加 Session 4 完整记录
f238b88 feat: 21 个新 builtin skill + pytest 测试套件 99 项 + README 用户手册
5f3baef refactor: CLI 重组为 sub-CLI 组（audio/memory/skills）
ebfa2b7 perf: task_planning 切到 deepseek-chat（14s -> 6s -> 1.6s 命中）
249df0e feat: 首次端到端验证通过 + LLM 自学习产出第一个 skill
52750f0 v2.0: 小张桌面语音助手完整骨架
```

## 目录结构（关键文件）

```
xiaozhang/
├── main.py                     CLI 入口（start/console/speak/status/mode/audio/memory/skills/vision/models）
├── dev_console.py              键盘 REPL
├── bench_llm.py                LLM 速度基准测试
├── config/
│   ├── runtime.yaml            运行时配置（音频/VAD/资源管理/游戏白名单/本地模型）
│   ├── llm.yaml                LLM provider + 路由（DeepSeek/Groq/Gemini）
│   ├── apps.yaml               本机软件路径映射（25+ 软件）
│   └── soul.md                 小张人设
├── src/
│   ├── audio/recorder.py       麦克风录音 + VAD + 声音反馈
│   ├── audio/stt.py            ASR（SenseVoice 优先 → faster-whisper fallback）
│   ├── audio/vad.py            VAD 抽象层（Silero 优先 → webrtcvad）
│   ├── audio/wake_word.py      唤醒词检测（待完善）
│   ├── brain/llm_router.py     多 provider 路由器（核心）
│   ├── brain/intent_classifier.py  轻量意图分类器（0ms 纯规则）
│   ├── brain/action_schema.py  Plan/Step pydantic 模型
│   ├── brain/prompts/          planner.md / skill_creator.md / intent_router.md
│   ├── core/config.py          双 YAML 配置加载
│   ├── core/state_machine.py   IDLE→ARMED→LISTENING→EXECUTING
│   ├── core/resource_manager.py 游戏感知 + 模型加载/卸载 + 延迟加载
│   ├── core/game_detector.py   4 种检测 + 自学习白名单
│   ├── core/cpu_guard.py       CPU 高负载守护协程
│   ├── actions/executor.py     三级降级调度
│   ├── actions/tier_d_protocol.py  D 级（URI/快捷键/cmd）
│   ├── actions/tier_c_uia.py   C 级（pywinauto/Playwright）
│   ├── actions/tier_a_vision.py A 级（OmniParser → Vision LLM）
│   ├── actions/douyin_actions.py 抖音专用操作
│   ├── skills/loader.py + matcher.py + generator.py + parser.py
│   ├── memory/store.py + recall.py + vector.py + user_profile.py
│   ├── learning/skill_stats.py + workflow_recorder.py + workflow_replay.py + evolution.py
│   ├── local_models/base.py + wake_word_model.py + vad_model.py + sensevoice_model.py + omniparser_model.py
│   ├── vision/screenshot.py + omniparser.py + vision_query.py
│   └── tray/tray_icon.py
├── skills/_builtin/            42 个内置 skill
├── skills/_generated/          LLM 自动学到的 skill
├── models/
│   ├── wake_word/              openWakeWord 模型 + 训练数据
│   ├── silero_vad.onnx         2.2MB
│   └── sensevoice_small.onnx   894MB
├── data/                       memory.db / chroma/ / USER.md
├── scripts/                    install_autostart.bat 等
├── tests/                      107 个 pytest
├── .env                        API keys（不进 git）
├── .kiro/steering/project-plan.md  v2.0 方案（Kiro 自动加载）
├── knowledge-dev.json          开发期状态
├── knowledge-runtime.json      运行期状态
└── session_log.md              开发会话日志
```

## 下一步优先级

1. **唤醒词实测验证** — ONNX 分类器已接入但从未成功触发过，需要 RMS 日志确认麦克风通路正常
2. **SenseVoice 推理对接** — 让 ASR 从 1.6s 降到 <0.5s（GPU 加速）
3. **更多应用的确定性操作** — 像抖音一样，为微信/QQ/B站 写专用 action
4. **声纹校验**（可选）— 防止别人触发你的小张

## 常用命令

```cmd
cd D:\11111begin\xiaozhang
uv run python main.py status          # 看资源/模型/模式
uv run python main.py skills list     # 看所有 skill
uv run python main.py speak "打开抖音" # 文字测试
uv run python main.py audio list      # 看麦克风
uv run python main.py memory recent   # 看历史
uv run pytest tests/ -q               # 跑测试（107 项 5 秒）
git log --oneline                     # 看 git 历史
```

## 2026-05-19 会话进展

- **修复 skill 匹配器 bug**：`matcher.py` 向量距离阈值从 `< 1.0` 改为 `< 0.35`，之前的阈值导致任意输入都被 ChromaDB 匹配到最近的向量（cancel skill），用户说"打开网页"也被执行"取消"
- **加入唤醒词调试日志**：`wake_word_loop.py` 新增静音块统计（每 30 块输出 RMS）、能量触发日志、分类器概率日志，方便诊断"为什么没反应"
- **守护进程已重启**：matcher fix 已生效，文字测试"打开网页"正确路由到 LLM 规划
- **待验证**：用户对着麦克风说"小张"能否触发唤醒词（RMS 日志会显示声音是否到达）

1. 项目的 steering 文件在 `.kiro/steering/project-plan.md`，Kiro 会自动加载
2. 所有架构决策在 `PLAN.md`
3. 开发进度在 `knowledge-dev.json` 和 `session_log.md`
4. **不要重复造轮子** — 先看已有代码再改
5. **fs_write 有时不落盘** — 写完后用 `cmd /c dir <path>` 验证文件真在硬盘上
6. **Windows GBK 编码问题** — Python 输出要 `sys.stdout.reconfigure(encoding="utf-8")`
7. **pyautogui 比 Vision 更可靠** — 对于已知 UI 布局的应用，用相对坐标操作
8. **测试前先删 `__pycache__`** — 避免旧 .pyc 缓存导致假通过
