---
name: train-wakeword
description: 录制唤醒词训练数据并重新训练模型
allowed-tools:
  - run_cmd
---

# train-wakeword

## triggers
- 训练唤醒词
- 重新训练小张
- 录制唤醒词
- 训练模型

## description
打开录音窗口让用户录制"小张"正样本或环境噪音负样本，然后重新训练 ONNX 分类器。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "say", "text": "打开训练窗口，请在新窗口中操作"},
  {"tier": "D", "action": "run_cmd", "cmd": ["pwsh", "-NoExit", "-WorkingDirectory", "D:\\11111begin\\xiaozhang", "-Command", "uv run python -u _train_wakeword.py"], "description": "打开正样本录制窗口"}
]
```

## learned
- 正样本录制脚本：_train_wakeword.py（录 30 次"小张"）
- 负样本录制脚本：_record_negative.py（录 15 分钟环境音）
- 训练脚本：_train_classifier.py（从 mel 特征训练 GradientBoosting → ONNX）
- 模型输出：models/wake_word/xiaozhang_wakeword.onnx（26KB）
- 当前准确率：99.8%（30 正 + 463 负）
- 追加样本后重新跑 _train_classifier.py 即可更新模型
