# 视觉交互 + 零 Token Skill 化 — 最终方案

> 2026-05-23 定稿，综合三份评估意见

---

## 核心思想

```
视觉推理（昂贵，只做一次）→ 编译成 deterministic skill（免费，永久复用）→ 最终淘汰视觉
```

传统 Computer Use：每次都在"看"
本系统：只在第一次"学习"，之后 0 token

---

## 架构三层

```
Runtime（执行层）     ← 本地 skill 命中，直接执行，0 token
Perception（感知层）  ← 第一次学习时用，本地模型，0 云端 token
Skill Compiler        ← 把感知结果编译成可重放的 deterministic steps
```

---

## 感知层优先级（从快到慢，从准到模糊）

| 优先级 | 方法 | 适用场景 | Token | 速度 |
|---|---|---|---|---|
| 1 | **Playwright DOM / CDP** | Chrome 网页 | 0 | < 0.1s |
| 2 | **pywinauto UIA 控件树** | Win32 程序（微信/WeGame） | 0 | < 0.2s |
| 3 | **YOLOv8 ONNX + EasyOCR** | 通用 UI 检测 | 0 | ~0.5s |
| 4 | **Florence-2**（暂不接） | 图标语义理解 | 0 | 太慢，AMD 不稳定 |

**关键决策：Florence-2 暂时不接。**
AMD 7900 XTX 上 DirectML 对 vision-language 模型支持不稳定，踩坑成本高。
EasyOCR（纯 CPU，0.3s）读按钮文字完全够用，不值得为 Florence-2 花时间。

---

## Skill 结构（JSON，不是 markdown 文本）

```json
{
  "name": "bilibili-play",
  "triggers": ["b站播放", "播放视频", "开始播放"],
  "method": "playwright",
  "selector": "button.bpx-player-ctrl-play",
  "fallback_method": "click_xy",
  "fallback_x": 1234,
  "fallback_y": 567,
  "learned_at": "2026-05-23",
  "fail_count": 0
}
```

Hermes 不参与执行，只参与学习阶段（第一次找选择器）。
执行时：本地 skill 匹配 → 直接调 xz.py → 0 token。

---

## xz.py 新增命令

```
# Phase 1（立刻可做）
xz.py playwright-click <selector>     Playwright 点击 CSS 选择器
xz.py chrome-click <描述>             CDP 接管 Chrome，找元素点击
xz.py click-xy <x> <y>               pyautogui 点击坐标

# Phase 2（需要 OmniParser ONNX）
xz.py screen-parse                    截屏 → YOLOv8+EasyOCR → 返回元素列表
xz.py find-element <描述>             从元素列表字符串匹配 → 返回坐标（不过 LLM）

# Phase 3
xz.py learn-click <描述>             完整学习：感知→点击→生成 skill
```

---

## OmniParser 模型转换方案

只转 YOLOv8（icon_detect），不转 Florence-2。

```python
# 方法：ultralytics 直接导出 ONNX（最简单）
from ultralytics import YOLO
model = YOLO("icon_detect.pt")  # 从 HuggingFace 下载 safetensors 后转 pt
model.export(format="onnx")
# 输出：icon_detect.onnx，可直接用 onnxruntime-directml 加载
```

文字识别用 EasyOCR（pip install easyocr，纯 CPU，0.3s）替代 Florence-2。

---

## 实现顺序

### Phase 1（今天可做，无阻塞）
- `xz.py playwright-click <selector>` 命令
- `xz.py click-xy <x> <y>` 命令
- Chrome CDP 接管（`--remote-debugging-port=9222`）
- 手动跑一遍 B站播放闭环，验证 skill 生成逻辑
- **目标：验证"第一次学习 → 第二次 0 token"完整闭环**

### Phase 2（需要先下载模型）
- 下载 OmniParser YOLOv8 safetensors → 转 ONNX
- 安装 EasyOCR
- `xz.py screen-parse` 命令
- 完整自动化：截屏 → 解析 → 字符串匹配 → 点击 → 生成 skill

### Phase 3（优化）
- Skill 失效检测（fail_count > 3 → 重新学习）
- 微信/WeGame pywinauto 补充
- 多分辨率适配

---

## 不做的事

- ❌ Florence-2（AMD 不稳定，EasyOCR 够用）
- ❌ Gemini Vision（省 token）
- ❌ 存绝对坐标（用选择器，坐标只作 fallback）
- ❌ 每次都走视觉（学会后本地化）
- ❌ transformers 训练依赖

---

## 成功标准

| 操作 | 第一次 | 第二次 |
|---|---|---|
| B站播放 | Playwright 找选择器 + 生成 skill（~2s，少量 token） | skill 命中，0 token，< 0.5s |
| 微信发送 | pywinauto 找控件 + 生成 skill | skill 命中，0 token，< 0.5s |
| 任意网页按钮 | CDP 找元素 + 生成 skill | skill 命中，0 token，< 0.5s |
| 本地程序按钮 | YOLOv8+EasyOCR 找元素 + 生成 skill（~1s） | skill 命中，0 token，< 0.5s |
