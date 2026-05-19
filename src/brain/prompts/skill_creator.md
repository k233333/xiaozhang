# 小张 — Skill Creator（任务成功后自动产出 SKILL.md）

任务执行成功后，调用本 prompt 把执行链固化为可复用的 skill。

## 输入

- `user_text`: 用户原话
- `intent`: 本次意图
- `executed_steps`: 实际成功执行的步骤（已包含 tier）
- `outcome`: 简短结果描述

## 输出

只输出一段 markdown，不要任何前后说明。结构如下：

```markdown
# <intent_human_readable>

## triggers
- <用户原话精简版>
- <近义触发词 1>
- <近义触发词 2>
- <近义触发词 3>

## description
<一句话描述这个 skill 做什么>

## confirm_required
false

## steps
\`\`\`json
[
  {"tier": "D", "action": "open_url", "url": "..."},
  ...
]
\`\`\`

## learned
- <从这次执行学到的小经验，比如某个 selector 的最佳写法>
```

## 规则

- triggers 至少 3 个，必须包含"动作 + 对象"两类关键词
- steps 必须能直接喂给 executor，不需要 LLM 再加工
- 如果原 plan 有 confirm_required=true 的步骤，整个 skill 也标 true
- 不要包含具体时间戳或会话 ID（这些放进 knowledge-runtime.json）
