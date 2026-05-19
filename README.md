# 小张（XiaoZhang）— Windows 桌面语音助手

> 常驻后台、纯终端运行的 Windows 桌面级语音助手。USB 麦克风 → faster-whisper STT → Claude Code（DeepSeek 后端）规划 → 三级降级执行。具备 Skills 自动生成 + Memory 跨会话回忆。越用越懂用户。

## 项目数据源结构（CClear 同款双层模式）

```
xiaozhang/
├── README.md                  ← 你正在看的这份（项目导航，永久不变）
├── PLAN.md                    ← v1.0 完整方案存档（架构决策书）
│
├── prompt-dev.md              ← 强模型 role：开发期助手（Claude Code / Kiro 用）
├── playbook-dev.md            ← 弱模型 step-by-step：开发期手册
├── knowledge-dev.json         ← 开发期可变状态：阶段进度 / 决策 / 学到的工程经验
│
├── prompt-runtime.md          ← 强模型 role：运行期小张大脑
├── playbook-runtime.md        ← 弱模型 step-by-step：运行期手册（给小张内置 LLM 用）
├── knowledge-runtime.json     ← 运行期可变状态：用户偏好 / skill 索引 / 应用映射
│
├── session_log.md             ← 开发会话归档（每次会话末尾追加）
│
├── skills/                    ← 运行期 skills（每个 skill 一个子目录）
│   ├── _builtin/              ← 手写的内置 skills
│   └── _generated/            ← agent 自动产出的 skills
│
├── data/                      ← 运行时数据（memory.db / chroma / USER.md）
└── src/                       ← Python 代码（D1 阶段开始填）
```

## 双层记忆体系

- **dev 层**：开发小张这个项目时的状态（架构决策、阶段进度、踩坑记录）
- **runtime 层**：小张运行时学到的东西（用户说"打开抖音"具体指什么、哪个 skill 能命中）

两层独立演进，互不污染。

## 全局路由触发词（写在 ~/.claude/CLAUDE.md 和 ~/.kiro/steering/xiaozhang.md）

当用户在 Claude Code / Kiro 里说出以下意图时，自动加载本项目数据源：

- "开发小张" / "小张开发" / "小张项目"
- "测试小张" / "调试小张"
- "继续小张" / "小张下一步"

触发后按 `playbook-dev.md` 执行，每步等用户确认。

## 当前进度

详见 `knowledge-dev.json` → `current_phase` 字段。

## 关键约束（不可妥协）

- 不部署本地大模型，全部 LLM 推理走 Claude Code（后端实际是 DeepSeek）
- 待机内存 < 100MB，CPU < 1%
- 无 GUI，纯终端 + 系统托盘
- 高风险操作必须二次确认（发消息、付款、删文件、关机等）

## 致谢

- Skills/Memory 设计灵感参考 [Hermes Agent (NousResearch, MIT)](https://github.com/NousResearch/hermes-agent)
- 项目工程范式继承自 `D:\11111begin\ttxx1\CClear`
