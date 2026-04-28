"""
SQLite database — all persistent data lives here.
Tables: days, commits_cache, memory, sprints, goals
"""
import sqlite3, json
from datetime import date, datetime, timedelta
from pathlib import Path
from agent.config import DATA_DIR

DB_PATH = DATA_DIR / "gitmind.db"

def _conn():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS days (
            date        TEXT PRIMARY KEY,
            status      TEXT DEFAULT 'pending',
            commit_msg  TEXT DEFAULT '',
            repos       TEXT DEFAULT '[]',
            notes       TEXT DEFAULT '',
            goal_hit    INTEGER DEFAULT 0,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS commits_cache (
            sha         TEXT PRIMARY KEY,
            repo        TEXT,
            message     TEXT,
            date        TEXT,
            files       TEXT DEFAULT '[]',
            additions   INTEGER DEFAULT 0,
            deletions   INTEGER DEFAULT 0,
            cached_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS memory (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS sprints (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date  TEXT,
            end_date    TEXT,
            goal        TEXT,
            status      TEXT DEFAULT 'active',
            retro       TEXT DEFAULT '',
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repo        TEXT,
            description TEXT,
            deadline    TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS blockers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repo        TEXT,
            description TEXT,
            detected_at TEXT,
            resolved    INTEGER DEFAULT 0
        );
        """)

# ── DAYS ──────────────────────────────────────────────────────

def get_day(d: str = None) -> dict | None:
    d = d or date.today().isoformat()
    with _conn() as c:
        row = c.execute("SELECT * FROM days WHERE date=?", (d,)).fetchone()
        return dict(row) if row else None

def upsert_day(status: str, commit_msg: str = "", repos: list = None, notes: str = ""):
    today = date.today().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO days (date, status, commit_msg, repos, notes, created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
                status=excluded.status,
                commit_msg=excluded.commit_msg,
                repos=excluded.repos,
                notes=excluded.notes
        """, (today, status, commit_msg, json.dumps(repos or []), notes, datetime.now().isoformat()))

def get_streak() -> int:
    with _conn() as c:
        rows = c.execute(
            "SELECT date, status FROM days ORDER BY date DESC LIMIT 60"
        ).fetchall()
    streak = 0
    for row in rows:
        if row["status"] == "committed":
            streak += 1
        elif row["status"] == "skipped":
            break
        # pending = don't break streak
    return streak

def get_calendar(n: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT date, status, commit_msg, repos FROM days ORDER BY date DESC LIMIT ?", (n,)
        ).fetchall()
    result = {r["date"]: dict(r) for r in rows}
    days = []
    for i in range(n - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        days.append(result.get(d, {"date": d, "status": "no_data"}))
    return days

def get_stats() -> dict:
    with _conn() as c:
        total   = c.execute("SELECT COUNT(*) FROM days").fetchone()[0]
        committed = c.execute("SELECT COUNT(*) FROM days WHERE status='committed'").fetchone()[0]
        skipped = c.execute("SELECT COUNT(*) FROM days WHERE status='skipped'").fetchone()[0]
    return {
        "streak": get_streak(),
        "committed": committed,
        "skipped": skipped,
        "total": total,
    }

# ── COMMITS CACHE ─────────────────────────────────────────────

def cache_commits(commits: list[dict]):
    with _conn() as c:
        for cm in commits:
            c.execute("""
                INSERT OR REPLACE INTO commits_cache
                (sha, repo, message, date, files, additions, deletions, cached_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                cm["sha"], cm["repo"], cm["message"], cm["date"],
                json.dumps(cm.get("files", [])),
                cm.get("additions", 0), cm.get("deletions", 0),
                datetime.now().isoformat()
            ))

def get_cached_commits(days: int = 7) -> list[dict]:
    since = (date.today() - timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM commits_cache WHERE date >= ? ORDER BY date DESC", (since,)
        ).fetchall()
    return [dict(r) for r in rows]

# ── MEMORY ────────────────────────────────────────────────────

def set_memory(key: str, value: str):
    with _conn() as c:
        c.execute("""
            INSERT INTO memory (key, value, updated_at) VALUES (?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, value, datetime.now().isoformat()))

def get_memory(key: str) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT value FROM memory WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

def get_all_memory() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM memory").fetchall()
    return {r["key"]: r["value"] for r in rows}

# ── SPRINTS ───────────────────────────────────────────────────

def create_sprint(goal: str, days: int = 7) -> int:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO sprints (start_date, end_date, goal, created_at)
            VALUES (?,?,?,?)
        """, (start, end, goal, datetime.now().isoformat()))
        return cur.lastrowid

def get_active_sprint() -> dict | None:
    with _conn() as c:
        row = c.execute("""
            SELECT * FROM sprints WHERE status='active'
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()
    return dict(row) if row else None

def close_sprint(sprint_id: int, retro: str):
    with _conn() as c:
        c.execute("UPDATE sprints SET status='done', retro=? WHERE id=?", (retro, sprint_id))

def get_all_sprints() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM sprints ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

# ── GOALS ─────────────────────────────────────────────────────

def add_goal(repo: str, description: str, deadline: str) -> int:
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO goals (repo, description, deadline, created_at)
            VALUES (?,?,?,?)
        """, (repo, description, deadline, datetime.now().isoformat()))
        return cur.lastrowid

def get_active_goals() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM goals WHERE status='active' ORDER BY deadline").fetchall()
    return [dict(r) for r in rows]

def complete_goal(goal_id: int):
    with _conn() as c:
        c.execute("UPDATE goals SET status='done' WHERE id=?", (goal_id,))
