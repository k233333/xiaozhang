"""pytest 全局 fixture

- 自动设 PYTHONPATH 指向 src/
- 每个测试自动用临时 data 目录，避免污染真实数据库
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    """每个测试用临时 data/ + knowledge-runtime.json，不污染真实状态"""
    # 临时 data 目录
    test_data = tmp_path / "data"
    test_data.mkdir()
    test_logs = tmp_path / "logs"
    test_logs.mkdir()

    # 不动 settings 实例，但通过 monkeypatch 改 paths 让 resolve 落到 tmp
    from src.core.config import settings as s  # noqa: PLC0415

    # 备份并切换路径
    monkeypatch.setattr(s.paths, "data_dir", str(test_data))
    monkeypatch.setattr(s.paths, "logs_dir", str(test_logs))
    monkeypatch.setattr(s.paths, "memory_db", str(test_data / "memory.db"))
    monkeypatch.setattr(s.paths, "user_profile", str(test_data / "USER.md"))
    monkeypatch.setattr(s.paths, "long_memory", str(test_data / "MEMORY.md"))
    # 测试环境关闭向量召回（ChromaDB 首次初始化要下载 embedding 模型，太慢）
    monkeypatch.setattr(s.memory, "enable_vector", False)

    # knowledge-runtime 也用临时
    kr = tmp_path / "knowledge-runtime.json"
    kr.write_text(
        json.dumps(
            {"skill_stats": {}, "auto_learned_games": [], "always_skill_match": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(s.paths, "knowledge_runtime", str(kr))

    yield


@pytest.fixture
def fake_skills_dir(tmp_path):
    """返回临时 skills/ 目录，写一个示例 SKILL.md"""
    builtin = tmp_path / "skills" / "_builtin"
    generated = tmp_path / "skills" / "_generated"
    builtin.mkdir(parents=True)
    generated.mkdir(parents=True)

    sample = builtin / "test-skill"
    sample.mkdir()
    (sample / "SKILL.md").write_text(
        """---
name: test-skill
description: 测试用 skill
---

# test-skill

## triggers
- 测试触发
- 测试一下

## description
这是一个测试 skill。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "open_url", "url": "https://example.com"}
]
```

## learned
- 这是一个测试条目
""",
        encoding="utf-8",
    )
    return tmp_path
