---
inclusion: always
---

# 小张（XiaoZhang）桌面语音助手 — 项目方案 v2.0

> 本文件由用户在 v2.0 阶段定稿，作为整个 workspace 的开发指导宪法。
> 任何后续架构修改必须更新本文件并在 `session_log.md` 记录。

## 一、项目概述

常驻 Windows 后台、纯终端运行的桌面级语音助手。USB 麦克风 → SenseVoice 中文 ASR → DeepSeek-V4-Pro（云端 API）规划 → 三级降级桌面自动化执行。

两大核心能力：
1. **越用越聪明** — Hermes/Friday 风格的 Skills 系统 + 三层 Memory，AI 完成任务后自动产出 SKILL.md，下次直接复用绕过 LLM
2. **游戏感知动态资源管理** — 检测到游戏运行时自动卸载本地模型释放显存，退出后重新加载；游戏帧数 0 影响

## 二、硬件目标

- CPU: AMD Ryzen 7 5800X
- 内存: 32GB
- GPU: AMD Radeon RX 7900 XTX (24GB VRAM)
- OS: Windows 10/11

## 三、核心设计决策

### 决策 1：纯云端 LLM
- 全部 LLM 推理走云端 API（DeepSeek 主力，未来加 Claude/Gemini/Groq）
- 用 YAML 配置 + LLMRouter 路由器统一管理多 API
- 通过 Skills 命中 + Memory 缓存节省 LLM 调用，而非靠本地小模型兜底

### 决策 2：本地仅部署"小而必要"模型，全部 ONNX + DirectML

| 模型 | 用途 | 后端 | 资源 |
|---|---|---|---|
| openWakeWord | 唤醒词检测 | CPU (ONNX) | 50MB / <1% CPU |
| Silero VAD | 静音检测 | CPU (ONNX) | 20MB / <0.4% CPU |
| SenseVoice-Small | 中文 ASR | DirectML (7900 XTX) | 234MB 内存 + 600MB 显存 |
| OmniParser-v2 | 屏幕元素解析 | DirectML (7900 XTX) | 1GB 内存 + 1.5GB 显存 |

**关键技术决策：DirectML + ONNX Runtime 取代 ROCm/PyTorch**
- ROCm Windows 还在 Preview，Adrenaline 升级会断兼容
- DirectML 是微软+AMD 联合优化，`pip install onnxruntime-directml` 一键安装
- 性能比 ROCm 仅低 5-10%，稳定性远高

### 决策 3：两段式中文唤醒词

```
IDLE （持续监听，CPU < 1%）
  ↓ 检测到 "小张"（置信度 > 0.6）
ARMED （4 秒倒计时，托盘黄灯，"叮"提示音）
  ↓ 听到 "你好" 或 "小张"   → LISTENING（绿灯）
  ↓ 4 秒超时               → IDLE
  ↓ 听到 "取消"             → IDLE
LISTENING （SenseVoice 流式转写）
  ↓ VAD 静音 1.5 秒
EXECUTING （命中 skill / Memory / 走 LLM 规划）
  ↓ 完成
IDLE
```

预期误触率：< 1 次/月

### 决策 4：三级降级桌面执行

| 级别 | 方式 | 延迟 | 成本 | 适用 |
|---|---|---|---|---|
| D | URI Scheme / 快捷键 / 命令行 | ~10ms | 0 | 最优，能用就用 |
| C | UIAutomation 控件树 / Playwright DOM | 100-500ms | 0 | D 失败时 |
| A | OmniParser 本地解析 → DeepSeek/Vision API | 800ms-2s | 极低 | C 失败时兜底 |

每步操作 LLM 在规划阶段就标注期望级别，执行失败自动降级。所有失败和降级写入 MEMORY.md，下次规划时知道"这个 app 走 D 没用，直接 C"。

### 决策 5：抄 Hermes Agent / Friday 三大模块

| 抄什么 | 来源 | 实现 |
|---|---|---|
| Skills 系统 | Hermes / Friday | 每个常用任务一个 SKILL.md，加载到 LLM system prompt 供匹配 |
| Skill 自动生成 | Hermes 的 skill-creator | 任务成功后自动产出新 SKILL.md 写入 skills/_generated/ |
| 三层 Memory | Friday 的 MemoryManager | Core / Archival / Conversation，SQLite + FTS5 |
| SOUL.md 人设外置 | Friday / OpenClaw | Markdown 多级覆盖（workspace > user > built-in） |
| 浏览器工作流录制回放 | Friday 的 BrowserRecorder | 录一次确定性回放，无 LLM 二次调用 |

### 决策 6：游戏感知动态资源管理（v2.0 核心新增）

**简化派模式：只有"标准模式"和"游戏模式"两种状态**

| 模式 | 加载的本地模型 | 内存 | 显存 | CPU 待机 | 端到端延迟 |
|---|---|---|---|---|---|
| 标准（默认） | 全部 4 个 + DirectML 加速 | ~1.5GB | ~2GB | 1-2% | 1-2s |
| 游戏（自动） | 仅 openWakeWord，ASR/Vision 走云端 | ~70MB | 0 | <1% | 3-4s（游戏中可接受）|

**切换触发条件**（任一命中即切换）：
1. 进程白名单匹配（最快）
2. 独占全屏检测（D3D 全屏游戏 100% 命中）
3. GPU 占用 > 50% 持续 10 秒（兜底）
4. CPU 占用 > 70% 持续 30 秒（高负载保护，自动转云端）
5. 用户手动开关（最高优先级）

**自学习游戏白名单**：
当条件 2 或 3 触发但条件 1 没命中时，自动记录前台进程名加入白名单。用户 0 维护成本。

### 决策 7：YAML 配置 + LLMRouter，多 API 易扩展

未来加新 LLM API 只改 YAML，代码 0 改动。

### 决策 8：高风险操作必须二次确认

发消息、付款、删文件、关机、提交含 PII 表单 — LLM 在规划阶段标注 `requires_confirmation: true`。

## 四、目录结构

```
xiaozhang/
├── main.py                              # 守护进程入口
├── pyproject.toml
├── config/
│   ├── llm.yaml                         # LLM Provider + 路由规则
│   ├── runtime.yaml                     # 资源管理 + 游戏白名单
│   └── soul.md                          # 小张的人设
├── src/
│   ├── audio/{wake_word,vad,recorder,stt}.py
│   ├── brain/
│   │   ├── llm_router.py                # 多 LLM 路由器（核心）
│   │   ├── prompts/{planner,skill_creator,intent_router}.md
│   │   └── action_schema.py
│   ├── memory/{store,vector,user_profile,recall}.py
│   ├── skills/{loader,matcher,generator,parser}.py
│   ├── vision/{screenshot,omniparser,vision_query}.py
│   ├── actions/{executor,tier_d_protocol,tier_c_uia,tier_a_vision}.py
│   ├── tray/tray_icon.py
│   ├── core/
│   │   ├── state_machine.py
│   │   ├── resource_manager.py          # 游戏感知动态资源管理 ★核心
│   │   ├── cpu_guard.py                 # CPU 高负载自动降级到云端
│   │   ├── game_detector.py             # 游戏运行检测（4 种方法）
│   │   ├── logger.py
│   │   └── safety.py
│   └── local_models/
│       ├── base.py                      # 统一接口（DirectML / CPU 切换 + unload）
│       ├── wake_word_model.py
│       ├── vad_model.py
│       ├── sensevoice_model.py
│       └── omniparser_model.py
├── skills/{_builtin,_generated}/
├── data/{memory.db,chroma/,USER.md,MEMORY.md}
├── models/                              # 本地 ONNX 模型文件
└── logs/
```

## 五、AMD 7900 XTX 适配方案

不用 ROCm，全部 DirectML。

模型 ONNX 来源：
- openWakeWord — 官方就是 ONNX
- Silero VAD — 官方提供 ONNX
- SenseVoice-Small — lovemefan/SenseVoice.cpp 发布页 / ModelScope
- OmniParser-v2 — microsoft/OmniParser-v2.0 提供官方 ONNX

统一加载接口（`src/local_models/base.py`）：
```python
import onnxruntime as ort
class LocalModel:
    def __init__(self, model_path, prefer_gpu=True):
        providers = []
        if prefer_gpu and 'DmlExecutionProvider' in ort.get_available_providers():
            providers.append('DmlExecutionProvider')
        providers.append('CPUExecutionProvider')
        self.session = ort.InferenceSession(model_path, providers=providers)
    def unload(self):
        del self.session
        self.session = None
        import gc; gc.collect()
```

## 六、CPU/GPU/内存承诺

**标准模式**（不打游戏）
- 待机：CPU 1-2% / 内存 1.5GB / 显存 2GB
- 触发任务：CPU 短峰值 5-8%
- 高 CPU 时自动降级到云端：CPU < 1% / 内存 70MB / 显存 0

**游戏模式**（自动触发）
- 持续：CPU < 1% / 内存 70MB / 显存 0
- 游戏帧数 0 影响

## 七、分阶段实施路线（两周拿到可演示版）

| 阶段 | 任务 | 产出 |
|---|---|---|
| D1 | 麦克风 → SenseVoice CPU → 终端打印 | 听觉链路通 |
| D2 | DeepSeek API + LLMRouter 骨架 | 大脑能用 |
| D3 | D 级 executor | 简单指令落地 |
| D4 | Skills 骨架 + SKILL.md 加载 | 学习能力雏形 |
| D5 | 三层 Memory（SQLite + FTS5 + ChromaDB） | 跨会话记忆 |
| D6 | C 级 executor | 复杂指令落地 |
| D7 | 自训练唤醒词 + 两段式状态机 | 真正"贾维斯感" |
| D8 | DirectML 加速：SenseVoice + OmniParser ONNX | GPU 加速到位 |
| D9 | A 级 executor：OmniParser → DeepSeek 视觉决策 | 鲁棒性 |
| D10 | 资源管理器 + 游戏检测 | 游戏感知 ★ |
| D11 | CPU 监控 + 自动降级到云端 | 高负载保护 |
| D12 | Skill 自动生成 | 自学习闭环 |
| D13 | 系统托盘 + 守护进程 + 端到端 demo | v0.1 可演示 |
| D14 | 测试 + 调优 + 文档 | v0.1 发布 |

## 八、参考开源项目（学习而非 fork）

| 项目 | 学什么 |
|---|---|
| Ascension-Yugi/Ascension (Friday) | 整体架构 + Skills + 三层 Memory（C# 思路完美匹配）|
| NousResearch/hermes-agent | SKILL.md 标准格式 + skill-creator 元 prompt |
| isair/jarvis | Echo detection + Tool router（Python）|
| dnhkng/GLaDOS | 低延迟音频管线 |
| FunAudioLLM/SenseVoice | 中文 ASR 主力 |
| microsoft/OmniParser | 屏幕解析 |
| KoljaB/RealtimeSTT | 流式 ASR 框架 |
| dscripka/openWakeWord | 唤醒词自训练 |
| wzpan/wukong-robot | 中文 ASR 经验 |

## 九、已知风险与应对

| 风险 | 严重度 | 策略 |
|---|---|---|
| 7900 XTX ROCm Windows 不稳定 | 高 | 完全不碰 ROCm，用 DirectML |
| 中文唤醒词模型缺失 | 中 | 自训练（30-50 段录音）|
| DeepSeek API 限流 / 网络波动 | 中 | Skills/Memory 命中覆盖 80%+ ；retry + fallback |
| 高 DPI 缩放 pyautogui 坐标偏移 | 中 | 启动时 SetProcessDpiAwareness(2) |
| 抖音网页版反爬 | 中 | 长期走客户端 + 快捷键路线 |
| 唤醒词误触 | 低 | 两段式 + 4 秒窗口 |
| 自动化操作误点 | 高 | 高风险二次确认 + 每步截图 |
| 游戏检测误判（OBS 直播误判为游戏）| 中 | 用户配置黑名单 |
| OmniParser 在某些应用识别差 | 中 | 三级降级，A 级失败回退云端 Vision |

## 十、最终一句话总结

> "打游戏时是隐形的，不打游戏时是丝滑的，越用越懂你的桌面贾维斯。"

技术核心：
- 本地少量小模型 + DirectML 加速（GPU）→ 1-2 秒响应
- 游戏自动卸载（释放显存）+ 云端兜底 → 游戏 0 影响
- Skills 自动生成 + 三层 Memory → 越用越聪明
- YAML 配置 + LLMRouter → 未来加新 API 0 代码改动
