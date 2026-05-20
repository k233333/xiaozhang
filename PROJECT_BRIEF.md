# 小张 项目简报 — 给接手 AI 的快速指南

> 写于 2026-05-20。项目路径：`D:\11111begin\xiaozhang\`

## 一句话

Windows 桌面语音助手"小张"。你说"小张"唤醒 → 语音指令 → LLM 规划 → 桌面上自动执行（打开软件、搜索、点击等）。v2.0 核心链路已跑通。

## 技术栈

- Python 3.11 + uv 包管理
- LLM：DeepSeek-Chat（主力）/ DeepSeek-Reasoner（复杂任务）/ Groq Llama-70B（fallback）/ Gemini 2.5 Flash（截屏分析）
- ASR：faster-whisper small CPU（1.6s 延迟）
- 桌面自动化：pyautogui + pywinauto + Playwright
- 记忆：SQLite + FTS5 + ChromaDB 向量召回
- GPU：7900 XTX 24GB，DirectML

## 当前状态（截止 2026-05-20）

### 能用的
- 语音录制 → faster-whisper 转写 → LLM 规划 → 桌面执行，全链路通
- 42 个 builtin skill（打开软件、系统控制、搜索等）
- LLM 自动学习新 skill（如"打开记事本"自动学成可复用 skill）
- 99.8% 自训练唤醒词 ONNX 模型已接入
- 抖音客户端搜索播放（pyautogui 确定性操作）
- 系统托盘 + 开机自启
- 107 个 pytest 测试

### 卡住的问题
1. **唤醒词未实测验证** — ONNX 模型接入了但从没成功触发过。刚加了调试日志（RMS/能量/分类器概率输出），需要用户对着麦克风说"小张"看日志。

## 立即任务：帮用户验证唤醒词

用户会说"帮我测一下小张的唤醒词"之类的话。你应该：

1. 先确认麦克风设备：`uv run python main.py audio list`
2. 启动主程序看日志：`uv run python main.py start`
3. 日志中有三个关键信息：
   - "静音块统计" — 每 30 个静音块出现一次，能看到 `last_rms` 值，确认麦克风有信号
   - "能量触发" — 用户说话时出现，显示 RMS 值
   - "分类器结果" — ONNX 模型打分，`prob >= wake_threshold` 才触发
4. 如果完全没有"能量触发"日志，说明麦克风没选对设备，需要改 `config/runtime.yaml` 里的 `audio.device_index`
5. 如果有"能量触发"但分类器 prob 很低（<0.3），说明唤醒词模型对用户声音不敏感，需要调整阈值或重新录训练数据

## 关键文件速查

```
config/
├── runtime.yaml      # 音频设备/VAD/唤醒词参数
├── llm.yaml          # LLM provider 路由
├── apps.yaml         # 本机软件路径映射
└── soul.md           # 小张人设

src/
├── audio/recorder.py        # 麦克风录音 + VAD + 叮嘟反馈
├── audio/wake_word_loop.py  # 唤醒词主循环（调试日志在这里）
├── audio/wake_word.py       # ONNX 分类器调用
├── brain/llm_router.py      # 多 provider 路由器
├── brain/intent_classifier.py  # 纯规则意图分类
├── actions/executor.py      # 三级降级执行 D/C/A
├── skills/matcher.py        # skill 匹配（向量+模糊，阈值 0.35）
├── memory/                  # SQLite+FTS5+ChromaDB
└── local_models/            # ONNX 模型加载（DirectML）

skills/_builtin/   # 42 个内置 skill
skills/_generated/ # LLM 自动生成的 skill
```

## 常用命令

```cmd
cd D:\11111begin\xiaozhang

uv run python main.py status          # 查看资源/模型/模式
uv run python main.py audio list      # 列出麦克风设备
uv run python main.py start           # 启动主循环
uv run python main.py speak "xxx"     # 文字测试（跳过语音）
uv run python main.py skills list     # 列出所有 skill
uv run python main.py memory recent   # 查看近期记忆
uv run pytest tests/ -q               # 跑测试（107 项，~5 秒）
```

## 重要提醒

- `fs_write` 有时不落盘，写完用 `cmd /c dir <path>` 验证
- pyautogui 比截图+Vision 更可靠，已知 UI 用确定性坐标
- 修改代码后先删 `__pycache__`，避免旧 .pyc 缓存
- API Keys 在 `.env` 里，不进 git
- 不要重复造轮子，先看已有代码再改
