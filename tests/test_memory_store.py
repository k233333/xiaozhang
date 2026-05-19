"""记忆库（SQLite + FTS5 中英文混合）测试"""
from __future__ import annotations

from src.memory import store


def test_init_db_creates_schema():
    store.init_db()
    # 第二次调用应该幂等
    store.init_db()


def test_session_lifecycle():
    store.init_db()
    sid = store.start_session(user_text="测试")
    assert sid > 0
    store.add_event(sid, "transcript", "测试用户输入")
    store.end_session(sid, intent="test_intent", success=True)

    sessions = store.recent_sessions(limit=5)
    assert len(sessions) >= 1
    matched = [s for s in sessions if s["id"] == sid]
    assert matched
    assert matched[0]["intent"] == "test_intent"
    assert matched[0]["success"] == 1


def test_search_chinese():
    store.init_db()
    sid = store.start_session("我想看不惑兄弟")
    store.add_event(sid, "transcript", "我想看不惑兄弟")
    store.end_session(sid, intent="watch_x", success=True)

    rows = store.search_events("不惑兄弟")
    assert any("不惑兄弟" in r["text"] for r in rows)
    rows = store.search_events("兄弟")
    assert any("兄弟" in r["text"] for r in rows)


def test_search_english():
    store.init_db()
    sid = store.start_session("open douyin")
    store.add_event(sid, "transcript", "open douyin search")
    store.end_session(sid, intent="x", success=True)

    rows = store.search_events("douyin")
    assert any("douyin" in r["text"] for r in rows)


def test_search_no_match():
    store.init_db()
    rows = store.search_events("根本不存在的内容 xyz")
    assert rows == []


def test_find_similar_intent():
    store.init_db()
    for _ in range(3):
        sid = store.start_session("打开抖音")
        store.add_event(sid, "transcript", "打开抖音")
        store.end_session(sid, intent="open_douyin", success=True)
    matches = store.find_similar_intent("open_douyin", limit=10)
    assert len(matches) == 3
    for m in matches:
        assert m["success"] == 1


def test_session_with_plan_json():
    """plan_json 字段能正确序列化/反序列化"""
    store.init_db()
    sid = store.start_session("x")
    plan_dict = {"intent": "test", "steps": [{"tier": "D", "action": "say"}]}
    store.end_session(sid, intent="test", success=True, plan_json=plan_dict)
    sessions = store.recent_sessions(limit=1)
    s = next(x for x in sessions if x["id"] == sid)
    import json
    parsed = json.loads(s["plan_json"])
    assert parsed["intent"] == "test"
