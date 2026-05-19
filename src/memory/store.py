"""SQLite + FTS5 持久化（事件流 / sessions / decisions）

设计仿 Hermes Agent 的 memory/store.py。表结构：

  sessions:    一条 = 一次完整唤醒到执行结束
  events:      一次 session 内的所有原子事件（语音、规划、执行、反馈）
  events_fts:  events.text 的 FTS5 全文索引

每次用户启动小张时建表（CREATE IF NOT EXISTS）。
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    ended_at REAL,
    intent TEXT,
    user_text TEXT,
    success INTEGER DEFAULT 0,
    skill_hit INTEGER DEFAULT 0,
    plan_json TEXT,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,           -- transcript / plan / step_start / step_end / error / feedback
    text TEXT,                    -- 主要文本内容（用于 FTS）
    payload TEXT,                 -- JSON 详情
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    text, content='events', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, text) VALUES('delete', old.id, old.text);
    INSERT INTO events_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


def _db_path() -> Path:
    p = settings.resolve_path(settings.paths.memory_db)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
    log.info("记忆库初始化完成", path=str(_db_path()))


def start_session(user_text: str = "") -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO sessions (started_at, user_text) VALUES (?, ?)",
            (time.time(), user_text),
        )
        return int(cur.lastrowid or 0)


def end_session(
    session_id: int,
    *,
    intent: str | None = None,
    success: bool = False,
    skill_hit: bool = False,
    plan_json: dict[str, Any] | None = None,
    note: str = "",
) -> None:
    with connect() as c:
        c.execute(
            """UPDATE sessions
               SET ended_at = ?, intent = ?, success = ?, skill_hit = ?, plan_json = ?, note = ?
               WHERE id = ?""",
            (
                time.time(),
                intent,
                int(success),
                int(skill_hit),
                json.dumps(plan_json, ensure_ascii=False) if plan_json else None,
                note,
                session_id,
            ),
        )


def add_event(
    session_id: int,
    kind: str,
    text: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO events (session_id, ts, kind, text, payload) VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                time.time(),
                kind,
                text,
                json.dumps(payload, ensure_ascii=False) if payload else None,
            ),
        )


def search_events(query: str, limit: int = 10) -> list[dict]:
    """事件全文检索

    SQLite FTS5 的 unicode61 不切中文词；本函数自动判断：
      - 含中文 → 走 LIKE 搜（性能可接受，事件量级 < 10 万）
      - 纯英文/数字 → 走 FTS5（更快、支持词缀）
    """
    q = query.strip()
    if not q:
        return []

    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in q)

    with connect() as c:
        if has_cjk:
            rows = c.execute(
                """SELECT id, session_id, ts, kind, text, payload
                   FROM events
                   WHERE text LIKE ?
                   ORDER BY ts DESC
                   LIMIT ?""",
                (f"%{q}%", limit),
            ).fetchall()
        else:
            fts_q = q if " " in q else f"{q}*"
            rows = c.execute(
                """SELECT events.id, events.session_id, events.ts, events.kind,
                          events.text, events.payload
                   FROM events_fts
                   JOIN events ON events.id = events_fts.rowid
                   WHERE events_fts MATCH ?
                   ORDER BY events.ts DESC
                   LIMIT ?""",
                (fts_q, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def recent_sessions(limit: int = 10) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def find_similar_intent(intent: str, limit: int = 3) -> list[dict]:
    """根据 intent 字面值查找历史成功 plan"""
    with connect() as c:
        rows = c.execute(
            """SELECT id, started_at, intent, user_text, plan_json, success, note
               FROM sessions
               WHERE intent = ? AND success = 1
               ORDER BY started_at DESC
               LIMIT ?""",
            (intent, limit),
        ).fetchall()
    return [dict(r) for r in rows]
