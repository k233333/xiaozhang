"""自学习迭代模块（受 Hermes self-evolution / GEPA 启发）

- skill_stats.py：每个 skill 的成功率/调用次数/最近一次失败原因
- workflow_recorder.py：把成功的 plan 自动转 skill（仿 Friday 的 BrowserRecorder）
- evolution.py：根据成功率重写 trigger / 拆分高失败率 skill
"""
