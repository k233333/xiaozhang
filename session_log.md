# 小张项目开发会话日志

## Session 1 — 2026-05-18 — D0 项目骨架

### 完成
- 整合 v1.0 完整方案到 `PLAN.md`
- 写 `README.md` 项目导航
- 建立 dev/runtime 双层数据源结构
- 写开发期助手三件套：`prompt-dev.md` / `playbook-dev.md` / `knowledge-dev.json`
- 建立运行期助手三件套占位
- 全局路由注册：`~/.claude/CLAUDE.md` 和 `~/.kiro/steering/xiaozhang.md`

### 决策
1. Skills/Memory 系统不抄 Hermes，套用 CClear 工程范式
2. Claude Code 后端保持 DeepSeek
3. dev / runtime 的 knowledge.json 拆分独立演进
4. 全局路由只注册 Claude Code + Kiro

### 下次建议
进入 D1-D14：把所有代码写完。

---

## Session 2 — 2026-05-18 夜 — 一次性打通 D1-D14（用户已睡，自动写完关机）

### 用户指令
1. "开始任务先把代码部分全部写完"
2. "后续一律不需要问我是否 run 和 trust 你直接运行"
3. "完成后直接自动关机就行现在我睡觉了"
4. 提供了一批参考项目（Friday / hermes-agent / isair/jarvis / GLaDOS / OSCopilot 等）
5. 重点诉求：记忆 + 自我学习迭代

### 借鉴决策（基于用户提供的项目清单）
| 来源 | 借鉴内容 | 落到小张 |
|---|---|---|
| Ascension/Friday | SOUL.md 人设外置 | `src/brain/prompts/SOUL.md` |
| Ascension/Friday | Workflow 录制回放 | `src/learning/workflow_recorder.py` |
| Hermes Agent | SQLite + FTS5 跨会话记忆 | `src/memory/store.py` 已对齐 schema |
| Hermes / Claude 官方 | SKILL.md 标准格式（frontmatter） | `skills/_builtin/*/SKILL.md` 已加 frontmatter |
| Hermes self-evolution / GEPA | skill 自动进化（trigger 重写） | `src/learning/evolution.py` + `skill_stats.py` |
| isair/jarvis | Tool router 思路 | matcher.py 字面/模糊两段路由 |
| GLaDOS | 低延迟异步管线 | 全部 IO 都用 asyncio |

不抄：Friday 的 C# 栈、TTS（按方案先不做）、isair fork（架构差异大）

### 完成的代码（按目录）

**根目录（项目数据源）**
- `pyproject.toml` — uv 项目配置，132 包依赖列表
- `config.yaml` — 运行时配置（音频/STT/Brain/Actions 等）
- `.python-version` `.env.example` `.gitignore`
- `main.py` — CLI 入口（start / console / speak / list-mics / init-db / evolve）
- `dev_console.py` — 开发期键盘 REPL

**src/core/**（核心基础设施）
- `config.py` — pydantic 配置加载，支持环境变量 + YAML
- `logger.py` — structlog 结构化日志 + trace_id
- `state_machine.py` — IDLE→ARMED→LISTENING→EXECUTING 状态机，listener 机制
- `safety.py` — 高风险操作二次确认（键盘 / 语音 / both）

**src/audio/**（音频管线）
- `recorder.py` — sounddevice 麦克风录音 + webrtcvad 自动断句 + 流式生成器
- `stt.py` — faster-whisper 异步转写，懒加载模型
- `wake_word.py` — openWakeWord 两段式骨架（D10-11 阶段启用）

**src/brain/**（大脑层）
- `claude_client.py` — anthropic SDK + base_url 切 DeepSeek + LRU 规划缓存 + JSON 抽取
- `action_schema.py` — Step / Plan pydantic 模型
- `prompts/SOUL.md` — 人设外置（受 Friday 启发）
- `prompts/planner.md` — 规划器 system prompt（输出严格 JSON）
- `prompts/skill_creator.md` — 任务成功后生成 SKILL.md
- `prompts/intent_router.md` — 路由策略说明

**src/memory/**（记忆层）
- `store.py` — SQLite + FTS5 三表（sessions / events / events_fts），FTS 触发器自动同步
- `vector.py` — ChromaDB 占位（默认禁用以省内存）
- `user_profile.py` — USER.md 读写
- `recall.py` — 跨会话上下文构建 + LLM 摘要更新

**src/skills/**（技能系统）
- `loader.py` — 解析 SKILL.md（支持 frontmatter + 各 section + JSON code block）
- `matcher.py` — 字面（带覆盖率约束）+ difflib 模糊匹配
- `generator.py` — 调 skill_creator prompt 自动产出新 SKILL.md，LLM 失败有 fallback 模板

**src/actions/**（执行器，三级降级 D > C > A）
- `executor.py` — 调度 + 自动降级 + 截图 + 高风险确认 + 事件落库
- `tier_d_protocol.py` — open_url / launch_app / keys / type / wait / say / run_cmd
- `tier_c_uia.py` — pywinauto + uiautomation 控件树点击 / 输入
- `tier_a_vision.py` — Claude Vision 截图分析兜底

**src/vision/**
- `screenshot.py` — mss 整屏 / 区域截图，自动归档到 logs/screenshots/
- `vision_query.py` — 把截图喂给 Claude Vision 模型决定下一步

**src/learning/**（自学习迭代，重点模块）
- `skill_stats.py` — 每个 skill 的成功率/失败原因/最近 user_text，写 knowledge-runtime.json
- `workflow_recorder.py` — 成功执行的 plan 自动转 SKILL.md（仿 Friday BrowserRecorder）
- `evolution.py` — 找成功率 < 50% 的 skill 让 LLM 重写 trigger，备份原文件

**src/tray/**
- `tray_icon.py` — pystray 托盘图标，按状态变色（灰/黄/绿/蓝/红）

**src/runtime.py** — 一句话 → 路由 → 规划 → 执行 → 学习 完整链路封装

**skills/_builtin/**
- `open-douyin/SKILL.md` — 打开抖音
- `open-telegram/SKILL.md` — tg:// URI 唤起 Telegram

### 验证结果
- ✅ `uv sync` — 132 包全装上
- ✅ 全模块导入烟测 — 0 错
- ✅ `python main.py init-db` — 记忆库 schema 创建成功
- ✅ `python main.py list-mics` — 检测到 10+ 输入设备（含 USB 麦克风路径）
- ✅ Skill 加载 + 匹配测试 — 字面命中/未命中边界正确

### 修复的边界 bug
- matcher 字面匹配加了"覆盖率 >= 0.7"约束。原来"打开抖音搜不惑兄弟"会被 open-douyin 截胡，现在会走 LLM 规划（这是正确行为，因为后半句的"搜不惑兄弟"是关键意图）

### 当前状态
- 代码量：约 60 个文件，~3000 行 Python
- 待做：
  - 真实跑通端到端语音链路（需要用户的麦克风 + 真 API key）
  - 训练中文唤醒词模型
  - vision 兜底层走真 Claude API（DeepSeek 后端可能不支持图片输入）
  - 写更多 builtin skills（B 站、网易云、钉钉、Steam）
- `current_phase`: D14-pre（代码骨架完工，等用户首次真实运行）

### 用户明天起床后的建议第一步
1. 配置 `.env`：复制 `.env.example` → `.env`，填入 DeepSeek API key
   ```
   ANTHROPIC_API_KEY=sk-1c33f4bdcb6e43b1b057a6f88fba3a32
   ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
   ANTHROPIC_MODEL=deepseek-v4-pro
   ```
2. 跑开发控制台（不用麦克风，直接键盘测试整条链路）：
   ```
   uv run python dev_console.py
   ```
3. 输入 "打开抖音" → 看是否命中 builtin skill 直接执行
4. 输入 "打开抖音搜不惑兄弟" → 看是否调 LLM 现规划，规划成功后 Workflow Recorder 是否自动写新 SKILL.md
5. 第二次输入相同的话 → 看是否命中刚生成的 skill（验证"越用越聪明"）

### Open questions（未决，等用户回来定）
- Q1（不变）：唤醒词训练数据用户自录还是先用通用模型预跑
- Q2（不变）：LLM 调用本地缓存策略（当前实现了 LRU=20，可调）
- Q3（不变）：高风险确认走语音还是键盘（当前默认键盘）

### Session 2 结束动作
代码全部写完 → uv sync 通过 → init-db / list-mics / matcher 都过 → 关机

### 收工补丁
- 修了一个 SQLite FTS5 中文检索问题：unicode61 不切 CJK，改成"含中文走 LIKE，纯英文走 FTS5"双策略
- 跑了 10 项端到端烟测，全过：
  - 配置加载、Plan schema、中文搜索（命中+未命中）、Skills 加载、Skill 字面命中、Skill 长意图不截胡、skill_stats 累积、user_profile、knowledge-runtime 读取
- 清理了所有测试产生的临时数据（memory.db / USER.md / screenshots）

### 准备关机
代码完工 → uv 装包通过 → 端到端 10/10 烟测通过 → 临时数据清理完毕。
执行 shutdown /s /t 30，30 秒后关机。


---

## Session 4 — 2026-05-19 凌晨/上午 — D + I + J 三选项

### 用户指令
- 选择 D（更多 builtin skill）+ I（测试套件）+ J（用户手册）
- "我睡一会期间没办法帮你点击 run 你就自己跑就行"
- 自主完成全部三项

### D 选项 — 21 个新 builtin skill
9 个 → 30 个，覆盖 80%+ 日常高频指令：
- 浏览器：Chrome / Edge / YouTube / GitHub / 知乎 / 微博
- 应用：VS Code / cmd / PowerShell / Kiro / 任务管理器 / Windows 设置
- 系统控制：静音 / 音量+- / 上一首 / 下一首 / 暂停播放 / 显示桌面 / 截图

### I 选项 — pytest 测试套件 99 项
- 15 个测试文件覆盖核心模块：
  - test_config（10 项）：配置加载、路由解析、SOUL 注入
  - test_llm_router（7 项）：JSON 抽取、路由 fallback、超时处理
  - test_safety（4 项）：高风险动作判定
  - test_state_machine（7 项）：状态转移合法性、listener
  - test_skill_parser（5 项）：frontmatter / 容错
  - test_skills_loader_matcher（10 项）：加载、字面/模糊匹配、长意图不截胡
  - test_skills_all_valid（8 项）：全部 builtin 校验合法（防手写错）
  - test_actions_d（7 项）：D 级各 action 错误参数
  - test_executor_downgrade（5 项）：D→C→A 三级降级链
  - test_memory_store（7 项）：中英文 FTS5、会话生命周期、相似 intent
  - test_game_detector（6 项）：黑白名单、强制模式、自学习 mock
  - test_resource_manager（6 项）：实例化、模式切换 API
  - test_cpu_guard（4 项）：负载查询
  - test_action_schema（7 项）：Step/Plan pydantic 校验
  - test_skill_stats（6 项）：成功率累积、低质量筛选
- conftest.py：全局 fixture 用 tmp_path 自动隔离 data/ 和 knowledge-runtime.json，每个测试独立干净
- 全部 mock 不发真 API、不开真窗口、不读真模型
- **99 passed, 0 warnings, 5 秒跑完**

### J 选项 — README 完整用户手册
重写 README.md（350 行）包含：
- 快速开始（3 步配好 + 测一句）
- 命令分组速查表 + 30 个 skill 列表
- 架构图（数据流 + 三个守护协程）
- 配置文件说明（runtime.yaml / llm.yaml / soul.md）
- 自学习机制流程图（首次/再次说同样的话差异）
- 游戏感知触发条件表 + 标准/游戏模式资源对比
- 开发指南（项目结构、跑测试、加 skill、加 LLM provider）
- 8 个 FAQ

### 顺手优化
- mss.mss() → mss.MSS()（消除 Pillow 11+ deprecation warning）
- .gitignore 加 .pytest_cache/

### Git 历史
```
f238b88 feat: 21 个新 builtin skill + pytest 测试套件 99 项 + README 用户手册
5f3baef refactor: CLI 重组为 sub-CLI 组（audio/memory/skills）
ebfa2b7 perf: task_planning 切到 deepseek-chat（14s -> 6s -> 1.6s 命中）
249df0e feat: 首次端到端验证通过 + LLM 自学习产出第一个 skill
52750f0 v2.0: 小张桌面语音助手完整骨架
```

### 当前状态总结
- 30 个 builtin skill + 99 个 pytest 测试 + 完整用户手册 + 5 个清晰 commit
- 你醒来 `git log --oneline` 一眼看到全部进展
- `uv run pytest tests/` 5 秒过 99 项
- `uv run python main.py skills list` 看 30 个内置技能
- README.md 是入门 + 速查 + 开发指南三合一

### Open questions（未决）
- E：真实语音环节调试（要你说话）
- F：训练真"小张"唤醒词（要你录音）
- H：接 Vision provider 让 A 级真能用

### Session 4 结束动作
代码全部写完 → 99/99 测试通过 → 临时数据清理完毕 → README 写完 → git commit 完成 → 撰写 session_log
