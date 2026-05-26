import * as fs from "fs";
import * as path from "path";
import initSqlJs, { Database } from "sql.js";

let SQL: initSqlJs.SqlJsStatic | undefined;

async function getSQL(): Promise<initSqlJs.SqlJsStatic> {
  if (SQL) return SQL;
  // sql.js ships the WASM next to its dist/ JS — point it at the node_modules copy.
  const wasmDir = path.join(__dirname, "..", "node_modules", "sql.js", "dist");
  SQL = await initSqlJs({ locateFile: (f: string) => path.join(wasmDir, f) });
  return SQL;
}

/**
 * Open the DB fresh from disk for each operation. Tiny DB, infrequent ops,
 * and this is how we stay coherent with concurrent Python writes from the
 * 6 PM tick / CLI / dashboard.
 */
async function openDb(dbFile: string): Promise<Database> {
  const sql = await getSQL();
  if (!fs.existsSync(dbFile)) {
    fs.mkdirSync(path.dirname(dbFile), { recursive: true });
    const db = new sql.Database();
    initSchema(db);
    flush(db, dbFile);
    return db;
  }
  const bytes = fs.readFileSync(dbFile);
  return new sql.Database(new Uint8Array(bytes));
}

function initSchema(db: Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS days (
      date TEXT PRIMARY KEY, status TEXT DEFAULT 'pending',
      commit_msg TEXT DEFAULT '', repos TEXT DEFAULT '[]',
      notes TEXT DEFAULT '', goal_hit INTEGER DEFAULT 0, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS commits_cache (
      sha TEXT PRIMARY KEY, repo TEXT, message TEXT, date TEXT,
      files TEXT DEFAULT '[]', additions INTEGER DEFAULT 0,
      deletions INTEGER DEFAULT 0, cached_at TEXT
    );
    CREATE TABLE IF NOT EXISTS memory (
      key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS sprints (
      id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT, end_date TEXT,
      goal TEXT, status TEXT DEFAULT 'active', retro TEXT DEFAULT '', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS goals (
      id INTEGER PRIMARY KEY AUTOINCREMENT, repo TEXT, description TEXT,
      deadline TEXT, status TEXT DEFAULT 'active', created_at TEXT
    );
  `);
}

function flush(db: Database, dbFile: string): void {
  const bytes = db.export();
  const tmp = dbFile + ".tmp";
  fs.writeFileSync(tmp, Buffer.from(bytes));
  fs.renameSync(tmp, dbFile);
}

function rowsOf(db: Database, sql: string, params: unknown[] = []): Record<string, unknown>[] {
  const stmt = db.prepare(sql);
  stmt.bind(params as initSqlJs.BindParams);
  const out: Record<string, unknown>[] = [];
  while (stmt.step()) out.push(stmt.getAsObject());
  stmt.free();
  return out;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function nowIso(): string {
  return new Date().toISOString();
}

// ── Public API ─────────────────────────────────────────────────────

export interface DayRow {
  date: string;
  status: "committed" | "skipped" | "pending" | "no_data";
  commit_msg: string;
  repos: string[];
  count?: number;
}

export interface Stats { streak: number; committed: number; skipped: number; total: number; }

export interface Goal {
  id: number;
  repo: string;
  description: string;
  deadline: string;
  status: string;
  created_at: string;
}

export interface Sprint {
  id: number;
  start_date: string;
  end_date: string;
  goal: string;
  status: string;
  retro: string;
}

export class GitlaneDb {
  constructor(private file: string) {}

  async getStats(): Promise<Stats> {
    const db = await openDb(this.file);
    try {
      const total = (rowsOf(db, "SELECT COUNT(*) AS n FROM days")[0]?.n as number) ?? 0;
      const committed = (rowsOf(db, "SELECT COUNT(*) AS n FROM days WHERE status='committed'")[0]?.n as number) ?? 0;
      const skipped = (rowsOf(db, "SELECT COUNT(*) AS n FROM days WHERE status='skipped'")[0]?.n as number) ?? 0;
      const rows = rowsOf(db, "SELECT date, status FROM days ORDER BY date DESC LIMIT 60");
      let streak = 0;
      for (const r of rows) {
        if (r.status === "committed") streak++;
        else if (r.status === "skipped") break;
      }
      return { streak, committed, skipped, total };
    } finally {
      db.close();
    }
  }

  async getActiveSprint(): Promise<Sprint | undefined> {
    const db = await openDb(this.file);
    try {
      const rows = rowsOf(db, "SELECT * FROM sprints WHERE status='active' ORDER BY created_at DESC LIMIT 1");
      return rows[0] as unknown as Sprint | undefined;
    } finally {
      db.close();
    }
  }

  async getActiveGoals(): Promise<Goal[]> {
    const db = await openDb(this.file);
    try {
      return rowsOf(db, "SELECT * FROM goals WHERE status='active' ORDER BY deadline") as unknown as Goal[];
    } finally {
      db.close();
    }
  }

  async getMemory(): Promise<Record<string, string>> {
    const db = await openDb(this.file);
    try {
      const out: Record<string, string> = {};
      for (const r of rowsOf(db, "SELECT key, value FROM memory")) {
        out[r.key as string] = r.value as string;
      }
      return out;
    } finally {
      db.close();
    }
  }

  async upsertDay(status: "committed" | "skipped" | "pending", commitMsg = "", repos: string[] = []): Promise<void> {
    const db = await openDb(this.file);
    try {
      const today = todayIso();
      db.run(
        `INSERT INTO days (date, status, commit_msg, repos, notes, created_at)
         VALUES (?, ?, ?, ?, '', ?)
         ON CONFLICT(date) DO UPDATE SET
           status=excluded.status, commit_msg=excluded.commit_msg, repos=excluded.repos`,
        [today, status, commitMsg, JSON.stringify(repos), nowIso()],
      );
      flush(db, this.file);
    } finally {
      db.close();
    }
  }

  async cacheCommits(commits: Array<{ sha: string; repo: string; message: string; date: string }>): Promise<void> {
    if (commits.length === 0) return;
    const db = await openDb(this.file);
    try {
      for (const c of commits) {
        db.run(
          `INSERT OR REPLACE INTO commits_cache (sha, repo, message, date, files, additions, deletions, cached_at)
           VALUES (?, ?, ?, ?, '[]', 0, 0, ?)`,
          [c.sha, c.repo, c.message, c.date, nowIso()],
        );
      }
      flush(db, this.file);
    } finally {
      db.close();
    }
  }
}
