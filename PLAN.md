# 小张 v1.0 完整方案（架构决策书）

> 整合所有对话决定，作为整个项目的指导宪法。任何后续修改必须更新本文件。

## 项目概述

一个常驻后台、纯终端运行的 Windows 桌面级语音助手，代号"小张"。通过外接 USB 麦克风接收语音指令，由 Claude Code（后端实际为 DeepSeek）作为大脑理解意图，结合三级降级的桌面自动化能力执行任务（开浏览器、搜抖音、控 Telegram、启动游戏等）。

具备 Skills 自动生成 + Memory 跨会话回忆两大能力，能将"打开抖音搜不惑兄弟最新视频"这类长指令逐步压缩为"我想看不惑兄弟"的一句话触发，越用越懂用户。

## 核心约束

- 不使用本地大模型（不部署 Ollama / vLLM / Hermes 模型权重）
- 全部 LLM 推理走 Claude Code（用户已配置后端为 DeepSeek）
- 待机内存 < 100MB，待机 CPU < 1%
- 无 GUI，纯终端 + 系统托盘图标

## 技术栈

| 层 | 选型 | 备注 |
|---|---|---|
| 语言 | Python 3.11+ | 核心逻辑 |
| 包管理 | uv | 比 pip 快 10x，纯净 |
| 唤醒词 | openWakeWord | 开源 + 支持自训练中文词 |
| 语音转写 | faster-whisper | small 模型，CPU 跑，1-2s 延迟 |
| VAD | webrtcvad 或 silero-vad | 自动断句 |
| 大脑 | Claude Code SDK | 后端 DeepSeek，统一无本地模型 |
| 桌面 UI 操作 | pywinauto + uiautomation | C 级降级 |
| 网页操作 | Playwright | C 级降级（网页） |
| 协议/快捷键 | subprocess、pyautogui、URI Scheme | D 级降级 |
| 视觉兜底 | Claude Vision (API) | A 级降级 |
| 记忆库 | SQLite + FTS5（仿 Hermes） + ChromaDB | 双层记忆 |
| 系统托盘 | pystray | 状态可视化 |
| 配置 | YAML | config.yaml |

## 目录结构（src/ 子树，D1 阶段开始填）

```
src/
├── audio/
│   ├── wake_word.py            # 两段式唤醒词检测（openWakeWord）
│   ├── recorder.py             # 麦克风录音 + VAD 自动断句
│   └── stt.py                  # faster-whisper 转写
├── brain/
│   ├── claude_client.py        # Claude Code SDK 封装
│   ├── prompts/
│   │   ├── planner.md          # 意图 → 操作 JSON
│   │   ├── skill_creator.md    # 任务完成后生成 skill
│   │   └── intent_router.md    # 决定走 memory / skill / 现规划
│   └── action_schema.py        # 操作 JSON 的 pydantic schema
├── memory/
│   ├── store.py                # SQLite + FTS5 持久化
│   ├── vector.py               # ChromaDB 语义召回
│   ├── user_profile.py         # USER.md 用户画像
│   └── recall.py               # 跨会话回忆 + LLM 摘要
├── skills/
│   ├── loader.py               # 加载 skills/ 下所有 SKILL.md
│   ├── matcher.py              # 触发词 + 语义匹配
│   └── generator.py            # 任务成功后自动生成 SKILL.md
├── vision/
│   ├── screenshot.py
│   └── vision_query.py
├── actions/
│   ├── executor.py             # 三级降级调度器
│   ├── tier_d_protocol.py      # D 级：URI Scheme / 快捷键 / cmd
│   ├── tier_c_uia.py           # C 级：pywinauto / Playwright
│   └── tier_a_vision.py        # A 级：Claude Vision 兜底
├── tray/
│   └── tray_icon.py
└── core/
    ├── state_machine.py        # IDLE→ARMED→LISTENING→EXECUTING
    ├── logger.py               # 结构化日志
    └── safety.py               # 高风险操作二次确认
```

## 核心架构决策

### 决策 1：纯云端 LLM，不上本地模型
- 用户已用 Claude Code（后端 DeepSeek），省去 GPU/ROCm 折腾
- CPU 跑 Whisper 完全够
- 省钱靠 Memory 命中 + Skill 复用，绕过 LLM 调用，而非本地小模型兜底

### 决策 2：两段式唤醒词

```
状态 IDLE （持续监听，CPU < 1%）
  ↓ 检测到 "小张"（置信度 > 0.6）
状态 ARMED （4 秒倒计时，托盘黄灯，"叮"提示音）
  ↓ 听到 "你好" 或 "小张"   → 进入 LISTENING（托盘绿灯）
  ↓ 4 秒超时               → 回到 IDLE（无声）
  ↓ 听到 "取消"             → 回到 IDLE
状态 LISTENING （faster-whisper 录音）
  ↓ VAD 静音 1.5 秒
状态 EXECUTING （交给 Claude / 命中记忆）
  ↓ 完成 / 失败
状态 IDLE
```

- 第一段：粗筛"小张"，低阈值，宁可多触发
- 第二段：4 秒窗口内必须再听到"你好"或"小张"
- 可选第三层：声纹粗筛（频域特征匹配本人）
- 预期误触：1 次/月 量级
- 训练数据：用户自录 30-50 段"小张" + 30 段"你好" + 200 段背景噪音

### 决策 3：三级降级执行（D > C > A）

| 级别 | 方式 | 延迟 | 成本 | 适用 |
|---|---|---|---|---|
| D | URI Scheme / 快捷键 / 命令行 | ~10ms | 0 | 最优，能用就用 |
| C | UIAutomation 控件树 / DOM selector | 100-500ms | 0 | D 失败时 |
| A | Claude Vision 截图分析 | 2-5s | $$ | C 失败时兜底 |

规划阶段 Claude 输出操作 JSON 时就标注期望级别，每步失败自动降级。所有失败和降级写入 knowledge-runtime.json，下次规划时知道"这个 app 走 D 没用，直接 C"。

### 决策 4：CClear 项目工程范式（替代 Hermes 移植）

不再硬抄 Hermes，而是把 CClear 验证过的双层模式平移：
- `knowledge-runtime.json` ↔ Hermes Memory schema
- `skills/<name>/SKILL.md` ↔ Hermes skills 目录
- `playbook-runtime.md` ↔ Hermes skill-creator prompt

CClear 已验证：knowledge.json 持续迭代 → 高频指令绕过 LLM → 节省 token。同样模式套到小张。

### 决策 5：Skill 与 Memory 协同流程

```
用户说："打开抖音搜不惑兄弟最新视频"
  ↓
1. STT 转写
2. Skill matcher：未命中
3. Memory recall：未命中
4. Claude 现规划 → 步骤 JSON
5. Executor 三级降级执行 → 成功
6. Skill generator 自动产出 SKILL.md：
     trigger: ["不惑兄弟", "看不惑兄弟", "抖音不惑"]
     steps: [...]
7. knowledge-runtime.json 追加 always_skill_match 索引

一周后用户说："我想看不惑兄弟"
  ↓
1. STT 转写
2. Skill matcher：触发词模糊匹配 → 命中（相似度 0.89）
3. 跳过 Claude，直接执行步骤 → 0.5 秒开始操作
4. 终端输出：🧠 命中 skill：watch_buhuxiongdi
```

### 决策 6：高风险操作必须二次确认

下列操作执行前必须语音/键盘确认：
- 发送消息 / 邮件
- 付款 / 输入验证码
- 删除文件 / 卸载程序
- 关闭/重启电脑
- 任何包含个人信息字段的表单提交

由 Claude 在规划阶段标注 `"requires_confirmation": true`，executor 看到后停下等用户确认。

## 已知风险与应对

| 风险 | 严重度 | 对应策略 |
|---|---|---|
| 7900 XTX 在 Windows 上 ROCm 支持差 | 低 | 不用 GPU，CPU 跑 Whisper small 完全够 |
| 高 DPI 缩放下 pyautogui 坐标偏移 | 中 | 启动时 `ctypes.windll.shcore.SetProcessDpiAwareness(2)` |
| 中文唤醒词模型缺失 | 中 | 自训练，文档化录音流程 |
| Claude API 限流 / 网络波动 | 中 | 本地命中（skill / memory）覆盖 80%+ 高频指令 |
| 抖音网页版反爬 | 中 | 长期走客户端 + 快捷键路线 |
| 唤醒词误触 | 低 | 两段式 + 4 秒窗口 + 声纹粗筛 |
| 自动化操作误点 | 高 | 高风险二次确认 + 每步操作前截图存档 |

## 分阶段实施路线

| 阶段 | 任务 | 预期产出 | 时长 |
|---|---|---|---|
| **D0** | 项目骨架 + 全局记忆路由 | 工程范式落地 | 0.5 天 |
| D1-2 | 麦克风 → faster-whisper → 终端打印 | 能听清说什么 | 1-2 天 |
| D3 | 接 Claude Code SDK，输出结构化 action JSON | 大脑能用 | 1 天 |
| D4-5 | D 级 executor：URI scheme、subprocess | 简单指令落地 | 2 天 |
| D6-7 | Skills + Memory 模块（仿 CClear/Hermes） | "越用越聪明"骨架 | 2 天 |
| D8-9 | C 级 executor：pywinauto + Playwright | 复杂指令落地 | 2 天 |
| D10-11 | openWakeWord 两段式唤醒 + 状态机 | 真正"贾维斯感" | 2 天 |
| D12-13 | A 级 executor：Claude Vision 兜底 + 失败降级 | 鲁棒性 | 2 天 |
| D14 | 系统托盘 + 守护进程 + 端到端 demo | 可演示版本 v0.1 | 1 天 |

之后迭代：声纹校验、Skill 自动进化（GEPA 思路）、跨设备同步、更多内置 SKILL。

## 资源占用预估

| 状态 | 内存 | CPU | 网络 |
|---|---|---|---|
| 待机（只跑 openWakeWord） | ~30MB | <1% | 0 |
| ARMED + 录音 | ~50MB | 5% | 0 |
| Whisper 转写（瞬时） | ~600MB | 30% 短峰值 | 0 |
| Skill/Memory 命中执行 | ~80MB | 5% | 0 |
| Claude 现规划执行 | ~80MB | 5% | API 流量 |

## 编码规范

- 命名：Python snake_case，类 CamelCase
- 注释中文，重点写清 prompt 设计意图、状态流转条件、降级策略
- 异步优先：唤醒监听、LLM 调用、自动化执行三条链路用 asyncio 解耦
- 必须有超时和重试：API 30s 超时、自动化操作 10s 超时
- 结构化日志：structlog，每步打 trace_id
- 类型注解：所有公开函数加 type hints + pydantic 校验
