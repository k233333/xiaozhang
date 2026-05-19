"""浏览器 Workflow 录制回放（仿 Friday BrowserRecorder）

核心思路：
  - 录制：用户手动操作浏览器时，Playwright 记录每一步（URL 导航 / 点击 / 输入 / 等待）
  - 回放：下次匹配到同一 skill 时，直接按录制的步骤确定性回放，无 LLM 二次调用

当前实现（v2.0 D5 阶段）：
  - 录制：从成功执行的 Plan 中提取浏览器相关步骤，序列化为 workflow JSON
  - 回放：加载 workflow JSON，按步骤执行（不需要 LLM）
  - 存储：每个 workflow 存在对应 skill 目录下的 workflow.json

后续迭代：
  - 真正的 Playwright 录制（用户操作时实时捕获 DOM 事件）
  - 条件分支（如果页面 A 出现就走路径 1，否则走路径 2）
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.brain.action_schema import Plan, Step
from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class WorkflowStep:
    """一步录制的操作"""

    action: str
    url: str | None = None
    text: str | None = None
    keys: str | None = None
    target: dict | None = None
    wait_ms: int = 0
    description: str = ""


@dataclass
class Workflow:
    """一个完整的录制工作流"""

    name: str
    created_at: float
    steps: list[WorkflowStep] = field(default_factory=list)
    source_intent: str = ""
    replay_count: int = 0
    last_replay_at: float | None = None


def record_from_plan(plan: Plan, *, skill_dir: Path | None = None) -> Path | None:
    """从成功执行的 Plan 提取 workflow 并保存

    只提取浏览器/UI 相关步骤（open_url / click / type / keys / wait）。
    如果 plan 只有 1 步 open_url，不值得录制（太简单）。
    """
    browser_steps: list[WorkflowStep] = []
    for step in plan.steps:
        if step.action in ("open_url", "click", "type", "keys", "wait"):
            ws = WorkflowStep(
                action=step.action,
                url=step.url,
                text=step.text,
                keys=step.keys,
                target=step.target,
                description=step.description,
            )
            browser_steps.append(ws)

    # 太简单不录（单步 open_url 已经被 builtin skill 覆盖）
    if len(browser_steps) <= 1:
        return None

    workflow = Workflow(
        name=plan.intent,
        created_at=time.time(),
        steps=browser_steps,
        source_intent=plan.intent,
    )

    # 保存位置
    if skill_dir is None:
        skill_dir = settings.resolve_path(settings.skills.generated_dir) / plan.intent
    skill_dir.mkdir(parents=True, exist_ok=True)
    wf_path = skill_dir / "workflow.json"

    data = {
        "name": workflow.name,
        "created_at": workflow.created_at,
        "source_intent": workflow.source_intent,
        "replay_count": 0,
        "steps": [
            {k: v for k, v in s.__dict__.items() if v is not None and v != "" and v != 0}
            for s in workflow.steps
        ],
    }
    wf_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("workflow 已录制", path=str(wf_path), steps=len(browser_steps))
    return wf_path


def load_workflow(skill_dir: Path) -> Workflow | None:
    """从 skill 目录加载 workflow.json"""
    wf_path = skill_dir / "workflow.json"
    if not wf_path.exists():
        return None
    try:
        data = json.loads(wf_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("workflow.json 读取失败", path=str(wf_path), err=str(e))
        return None

    steps = []
    for raw in data.get("steps", []):
        steps.append(WorkflowStep(
            action=raw.get("action", ""),
            url=raw.get("url"),
            text=raw.get("text"),
            keys=raw.get("keys"),
            target=raw.get("target"),
            wait_ms=raw.get("wait_ms", 0),
            description=raw.get("description", ""),
        ))

    return Workflow(
        name=data.get("name", ""),
        created_at=data.get("created_at", 0),
        steps=steps,
        source_intent=data.get("source_intent", ""),
        replay_count=data.get("replay_count", 0),
        last_replay_at=data.get("last_replay_at"),
    )


def workflow_to_plan(workflow: Workflow) -> Plan:
    """把 workflow 转成 Plan 对象，供 executor 直接执行"""
    steps: list[Step] = []
    for ws in workflow.steps:
        step_data: dict = {
            "tier": "D",
            "action": ws.action,
            "description": ws.description,
        }
        if ws.url:
            step_data["url"] = ws.url
        if ws.text:
            step_data["text"] = ws.text
        if ws.keys:
            step_data["keys"] = ws.keys
        if ws.target:
            step_data["target"] = ws.target
        if ws.wait_ms:
            step_data["timeout_seconds"] = ws.wait_ms / 1000.0
        steps.append(Step.model_validate(step_data))

    return Plan(
        intent=workflow.source_intent,
        skill_hit=True,
        skill_name=workflow.name,
        steps=steps,
        note=f"workflow 回放（第 {workflow.replay_count + 1} 次）",
    )


def increment_replay_count(skill_dir: Path) -> None:
    """回放成功后 +1"""
    wf_path = skill_dir / "workflow.json"
    if not wf_path.exists():
        return
    try:
        data = json.loads(wf_path.read_text(encoding="utf-8"))
        data["replay_count"] = data.get("replay_count", 0) + 1
        data["last_replay_at"] = time.time()
        wf_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.debug("更新 replay_count 失败", err=str(e))
