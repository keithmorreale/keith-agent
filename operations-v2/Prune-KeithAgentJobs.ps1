param(
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$Python = "C:\KeithAgent\.coord-venv\Scripts\python.exe"
$Db = "C:\KeithAgent\data\keith-agent.db"

if (-not (Test-Path $Python)) {
    throw "Python not found: $Python"
}

if (-not (Test-Path $Db)) {
    throw "Database not found: $Db"
}

$env:KEITH_AGENT_DB = $Db
$env:KEITH_AGENT_RETENTION_DAYS = [string]$RetentionDays

$PythonCode = @"
import os
import sqlite3
from datetime import datetime, timezone, timedelta

db = os.environ["KEITH_AGENT_DB"]
days = int(os.environ["KEITH_AGENT_RETENTION_DAYS"])
cutoff = datetime.now(timezone.utc) - timedelta(days=days)

con = sqlite3.connect(db)
cur = con.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info(jobs)").fetchall()]

if "status" not in cols:
    raise SystemExit("jobs.status column not found")

if "completed_at" in cols:
    date_col = "completed_at"
elif "created_at" in cols:
    date_col = "created_at"
else:
    raise SystemExit("No created_at/completed_at column found")

rows = cur.execute(
    f"SELECT rowid, status, {date_col} "
    "FROM jobs WHERE status IN ('completed','failed')"
).fetchall()

delete_ids = []

for rowid, status, value in rows:
    if not value:
        continue

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if dt.astimezone(timezone.utc) < cutoff:
            delete_ids.append((rowid,))
    except Exception:
        pass

if delete_ids:
    cur.executemany(
        "DELETE FROM jobs WHERE rowid=?",
        delete_ids
    )
    con.commit()
    cur.execute("VACUUM")
    con.commit()

print(
    f"Deleted {len(delete_ids)} completed/failed jobs "
    f"older than {days} days."
)

con.close()
"@

$PythonCode | & $Python -

if ($LASTEXITCODE -ne 0) {
    throw "Job retention failed."
}
