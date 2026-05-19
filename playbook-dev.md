# 小张项目 — 开发期 Playbook（弱模型逐步手册）

> 给 DeepSeek / 本地小模型等能力较弱的 agent 用。
> 每一步明确"输入是什么 → 做什么 → 输出什么"，不需要模型自由推理。

---

## Step 0：加载上下文

```
输入：项目根目录 D:\11111begin\xiaozhang
做：
  1. 读取 PLAN.md（只读架构决策章节）
  2. 读取 knowledge-dev.json
  3. 读取 session_log.md 末尾 50 行

输出：
  - 当前阶段：knowledge-dev.json → current_phase
  - 上次结束动作：session_log.md 最后一条记录
  - 待解决问题数量：knowledge-dev.json → open_questions 长度
```

## Step 1：报告状态并等指令

```
输出格式：
  📍 当前阶段：D<N> — <阶段名>
  📋 上次结束于：<最近一条 session_log>
  ❓ 待解决问题：<N> 个
  💡 建议下一步：<根据 PLAN.md 路线>

  你想怎么做？
    A. 推进阶段任务
    B. 讨论 open_questions
    C. 自由提问
等待用户回复
```

## Step 2：推进阶段任务（用户选 A）

```
对当前阶段（如 D1-2：麦克风 → Whisper → 终端打印）：

  2.1 列出该阶段子任务（从 PLAN.md 阶段表）
  2.2 询问用户从哪个子任务开始
  2.3 创建对应文件，写最小可用版本
  2.4 让用户跑一下看是否工作
  2.5 用户确认通过 → 跳 Step 5 更新进度
  2.6 用户报错 → 跳 Step 4 排错
```

## Step 3：讨论 open_questions（用户选 B）

```
读取 knowledge-dev.json → open_questions
逐条展示：
  ❓ Q<N>：<问题描述>
     上下文：<context>
     可选答案：<options>
等用户给出答案后：
  - 把这条从 open_questions 移到 decisions
  - 在 decisions 里写：question / answer / rationale / date
保存
```

## Step 4：排错

```
对用户报告的错误：
  4.1 让用户贴完整报错栈
  4.2 检查是否在 knowledge-dev.json → learned 里有同类问题
       命中 → 直接给方案
       未命中 → 现场分析
  4.3 修复后追加到 learned：
       {issue, root_cause, fix, date}
```

## Step 5：更新进度

```
完成一个子任务后：
  5.1 在 knowledge-dev.json → phase_log 追加：
       {phase, sub_task, completed_at, output_files}
  5.2 如果整个阶段完成，更新 current_phase = 下一个阶段
  5.3 在 session_log.md 末尾追加一段：
       ## YYYY-MM-DD Session N
       完成：<子任务>
       产出：<文件列表>
       下次：<建议下一步>
```

## Step 6：记录工程经验

```
当遇到以下情况之一，追加到 knowledge-dev.json → learned：
  - 库版本兼容问题（如 faster-whisper 在 Windows 上的 CUDA 12 坑）
  - API 行为不符合文档（如 Claude Code SDK 某参数的真实表现）
  - 性能优化技巧（如 openWakeWord 的内存占用降低方法）
  - 架构权衡决策（"为什么 D6-7 选 SQLite 而不是 LMDB"）

格式：
  {
    "rule": "一句话规则",
    "context": "什么情况下适用",
    "evidence": "证据来源（链接/报错信息）",
    "date": "YYYY-MM-DD"
  }
```

## Step 7：会话结束清单

```
用户说"今天到这"或"先停一下"时：
  [ ] knowledge-dev.json 是否已更新？
  [ ] session_log.md 是否已追加本次记录？
  [ ] 有未保存的代码改动吗？
  [ ] 需要把什么追加到 open_questions 留给下次吗？

逐项确认后告别。
```

---

## 关键约束（每一步检查）

- [ ] 是否已读 knowledge-dev.json？不能凭记忆做事
- [ ] 是否在用户确认下推进？不要跳阶段
- [ ] 改动后是否更新了对应 json 字段？
- [ ] 不写测试除非用户要求（D14 之前都是 demo）
- [ ] 不安装本地大模型依赖
