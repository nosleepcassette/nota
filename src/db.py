# maps · cassette.help · MIT
"""
nota database layer — SQLite schema and CRUD.

Dependency direction convention:
  task_relations row: (task_id=PARENT, related_id=CHILD, relation_type='depends_on')
  means PARENT cannot be completed until CHILD is done.
  In inline syntax: "parent -> child" = parent depends_on child.
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(os.environ.get("NOTA_DB", Path.home() / ".nota" / "nota.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    project     TEXT NOT NULL DEFAULT 'inbox',
    scope       TEXT NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 3,
    due_date    TEXT DEFAULT NULL,
    status      TEXT NOT NULL DEFAULT 'todo',
    parent_id   INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS task_relations (
    task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    related_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    PRIMARY KEY (task_id, related_id, relation_type)
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (task_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# ── writes ────────────────────────────────────────────────────────────────────

def task_create(
    title: str,
    body: str = "",
    project: str = "inbox",
    scope: str = "",
    priority: int = 3,
    due_date: Optional[str] = None,
    parent_id: Optional[int] = None,
    tags: Optional[List[str]] = None,
) -> int:
    """Insert a task. Returns the new task id."""
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, body, project, scope, priority, due_date, parent_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, body, project, scope, priority, due_date, parent_id, now, now),
        )
        task_id = cur.lastrowid
        for tag in (tags or []):
            conn.execute(
                "INSERT OR IGNORE INTO task_tags (task_id, tag) VALUES (?, ?)",
                (task_id, tag),
            )
        return task_id


def task_relate(task_id: int, related_id: int, relation_type: str) -> None:
    """
    Add a relation between two tasks.

    relation_type options:
      depends_on  — task_id cannot be completed until related_id is done
      blocks      — task_id blocks related_id (inverse of depends_on)
      related_to  — bidirectional association, no ordering implication
      part_of     — task_id is a component of related_id (different from subtask/parent_id)
    """
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO task_relations (task_id, related_id, relation_type) VALUES (?, ?, ?)",
            (task_id, related_id, relation_type),
        )


def task_done(task_id: int) -> bool:
    """Mark a task complete. Returns False if task not found."""
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE tasks SET status='done', updated_at=? WHERE id=? AND status != 'done'",
            (now, task_id),
        )
        return cur.rowcount > 0


def task_update(task_id: int, **fields) -> bool:
    """
    Update arbitrary fields on a task.
    Allowed: title, body, project, scope, priority, due_date, status, parent_id
    """
    allowed = {"title", "body", "project", "scope", "priority", "due_date", "status", "parent_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = int(time.time())
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [task_id]
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", vals)
        return cur.rowcount > 0


def task_tag_add(task_id: int, tag: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO task_tags (task_id, tag) VALUES (?, ?)",
            (task_id, tag),
        )


# ── reads ─────────────────────────────────────────────────────────────────────

def task_get(task_id: int) -> Optional[Dict[str, Any]]:
    """Return full task dict with tags, subtasks, and relations. None if not found."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        t = dict(row)
        t["tags"] = [r["tag"] for r in conn.execute(
            "SELECT tag FROM task_tags WHERE task_id=?", (task_id,)
        )]
        t["subtasks"] = [dict(r) for r in conn.execute(
            "SELECT id, title, status, priority FROM tasks WHERE parent_id=? ORDER BY created_at ASC",
            (task_id,),
        )]
        t["relations"] = [
            {
                "related_id": r["related_id"],
                "relation_type": r["relation_type"],
                "title": r["title"],
                "status": r["status"],
            }
            for r in conn.execute(
                "SELECT tr.related_id, tr.relation_type, t.title, t.status "
                "FROM task_relations tr JOIN tasks t ON t.id = tr.related_id "
                "WHERE tr.task_id=?",
                (task_id,),
            )
        ]
        return t


def task_list(
    project: Optional[str] = None,
    scope: Optional[str] = None,
    priority: Optional[int] = None,
    status: str = "todo",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Return tasks matching filters, ordered by priority asc then due_date asc."""
    where = ["t.status = ?"]
    params: List[Any] = [status]
    if project:
        where.append("t.project = ?")
        params.append(project)
    if scope:
        where.append("t.scope = ?")
        params.append(scope)
    if priority is not None:
        where.append("t.priority = ?")
        params.append(priority)
    sql = (
        f"SELECT t.*, GROUP_CONCAT(tt.tag, ',') as tags_str "
        f"FROM tasks t LEFT JOIN task_tags tt ON tt.task_id = t.id "
        f"WHERE {' AND '.join(where)} "
        f"GROUP BY t.id "
        f"ORDER BY t.priority ASC, t.due_date ASC NULLS LAST, t.created_at ASC "
        f"LIMIT ?"
    )
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        t = dict(row)
        t["tags"] = [x for x in (t.pop("tags_str") or "").split(",") if x]
        result.append(t)
    return result


def task_find_by_title(title: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Find the most recent open task matching title (case-insensitive prefix/exact)."""
    with get_conn() as conn:
        params: List[Any] = [title.lower(), f"%{title.lower()}%"]
        extra = ""
        if project:
            extra = " AND LOWER(project) = ?"
            params.append(project.lower())
        row = conn.execute(
            f"SELECT * FROM tasks WHERE (LOWER(title) = ? OR LOWER(title) LIKE ?){extra} "
            f"AND status='todo' ORDER BY created_at DESC LIMIT 1",
            params,
        ).fetchone()
        return dict(row) if row else None


def projects_list() -> List[Dict[str, Any]]:
    """Return projects with open task counts, sorted by count desc."""
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT project, COUNT(*) as count FROM tasks WHERE status='todo' "
                "GROUP BY project ORDER BY count DESC"
            )
        ]
