# 小张运行期 — 弱模型 Playbook

> 给运行期内嵌的弱模型用（如果未来某天要本地小模型兜底）。
> D6-7 阶段才会真正接入。当前是占位。

---

## Step 0：加载上下文

```
输入：用户语音转写后的文本
做：
  1. 读 knowledge-runtime.json → always_skill_match
  2. 读 data/USER.md（用户画像，如有）
输出：
  匹配到的 skill 名 / 未匹配
```

## Step 1：skill 匹配

```
对 always_skill_match 中每个条目：
  1. 计算用户输入与 trigger 关键词的相似度
  2. 相似度 > 0.85 → 命中
若命中：
  跳到 Step 3 直接执行 skill 步骤
若未命中：
  跳到 Step 2 现规划
```

## Step 2：现规划（调用大脑）

```
向 Claude Code SDK 发送：
  - 系统 prompt：prompt-runtime.md 全文
  - 用户输入：转写文本
  - 上下文：USER.md + 近期 session_log

接收 JSON：
  解析为 steps 数组
  对每个 step 标注 tier
  对高风险 step 标注 confirm_required
```

## Step 3：执行步骤

```
对每个 step：
  3.1 检查 confirm_required → 等用户确认
  3.2 按 tier 执行
       D 失败 → 降级 fallback_tier
       C 失败 → 降级 A
       A 失败 → 上报"无法完成"
  3.3 记录每步结果
```

## Step 4：结果反馈

```
执行成功：
  - 简短播报（"好，已为你打开抖音"）
  - 如果是新规划（非 skill 命中），调用 skill_creator 生成 SKILL.md
执行失败：
  - 简短播报失败原因
  - 写 knowledge-runtime.json → failed_attempts，下次规划时 LLM 会避开同样路径
```

## Step 5：skill 自动生成

```
非 skill 命中的成功执行 → 调 LLM 生成 SKILL.md：
  - trigger: 提取 3-5 个关键词
  - steps: 复用本次执行链
  - 写入 skills/_generated/<intent_slug>/SKILL.md
  - 在 knowledge-runtime.json → always_skill_match 追加索引项
```

---

## 关键约束

- [ ] 优先 skill 命中，避开 LLM
- [ ] 每个高风险 step 必须 `confirm_required: true`
- [ ] 失败降级链：D → C → A → 上报
- [ ] 成功执行后必须写 skill（除非 skill 命中本身）
- [ ] LLM 调用 30s 超时
- [ ] 自动化操作 10s 超时
