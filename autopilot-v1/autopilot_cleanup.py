
from __future__ import annotations
import argparse, csv, hashlib, json, os, shutil, sqlite3, subprocess, sys, time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(r"C:\KeithAgent")
REPORTS = BASE / "reports"
STATE = BASE / "autopilot"
DB = STATE / "autopilot.db"
POLICY_PATH = BASE / "autopilot_policy.json"

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def load_policy():
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def init_db():
    STATE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS runs(
      run_id TEXT PRIMARY KEY,
      started_at TEXT,
      completed_at TEXT,
      status TEXT,
      files_seen INTEGER DEFAULT 0,
      bytes_seen INTEGER DEFAULT 0,
      duplicate_groups INTEGER DEFAULT 0,
      quarantined_files INTEGER DEFAULT 0,
      quarantined_bytes INTEGER DEFAULT 0,
      review_items INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS review_queue(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT,
      created_at TEXT,
      reason TEXT,
      path TEXT,
      details TEXT,
      status TEXT DEFAULT 'OPEN'
    );
    CREATE TABLE IF NOT EXISTS quarantine_manifest(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT,
      created_at TEXT,
      source_path TEXT,
      quarantine_path TEXT,
      retained_path TEXT,
      size INTEGER,
      sha256 TEXT,
      verified INTEGER DEFAULT 0
    );
    """)
    con.commit()
    return con

def fixed_drives():
    # Windows fixed disks = DriveType 3
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
        "Select-Object -ExpandProperty DeviceID"
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    drives = [x.strip() + "\\" for x in p.stdout.splitlines() if x.strip().endswith(":")]
    return drives

def excluded(path: Path, policy):
    parts = {p.lower() for p in path.parts}
    for name in policy["exclude_directory_names"]:
        if name.lower() in parts:
            return True
    if path.name.lower() in {x.lower() for x in policy["exclude_file_names"]}:
        return True
    return False

def protected_tree(path: Path, policy):
    s = str(path).lower()
    for m in policy["protected_markers"]:
        if m.lower() in s:
            return True
    return False

def walk_drive(root: Path, policy):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    p = Path(e.path)
                    if excluded(p, policy):
                        continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if protected_tree(p, policy):
                                continue
                            stack.append(p)
                        elif e.is_file(follow_symlinks=False):
                            if not excluded(p, policy):
                                try:
                                    st = e.stat(follow_symlinks=False)
                                    yield p, st.st_size, st.st_mtime
                                except OSError:
                                    pass
                    except OSError:
                        pass
        except (PermissionError, FileNotFoundError, OSError):
            continue

def sha256_file(path: Path, block=8*1024*1024):
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()

def priority(path: str, policy):
    p = path.lower()
    # Lower numeric value = better canonical destination.
    for i, token in enumerate(policy["canonical_priority"]):
        if ("\\" + token.lower() + "\\") in p or p.endswith("\\" + token.lower()):
            base = i
            break
    else:
        base = 100
    penalty = 0
    for tok in policy["low_priority_tokens"]:
        if tok.lower() in p:
            penalty += 100
    return base + penalty

def choose_canonical(items, policy):
    ranked = sorted(items, key=lambda x: (priority(x["path"], policy), x["path"].lower()))
    best = ranked[0]
    # Avoid automatic decisions if everything is in low-confidence locations.
    if priority(best["path"], policy) >= 100:
        return None
    return best

def add_review(con, run_id, reason, path, details):
    con.execute(
        "INSERT INTO review_queue(run_id,created_at,reason,path,details) VALUES (?,?,?,?,?)",
        (run_id, utcnow(), reason, path, json.dumps(details, ensure_ascii=False))
    )
    con.commit()

def safe_quarantine(source: Path, retained: Path, expected_hash: str, run_id: str, policy, con):
    drive_root = Path(source.anchor)
    qroot = drive_root / policy["quarantine_root_name"] / run_id
    rel = Path(str(source)[len(source.anchor):].lstrip("\\/"))
    target = qroot / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    # Re-verify both before moving.
    if not source.exists() or not retained.exists():
        raise RuntimeError("Source or retained copy disappeared before quarantine.")
    if sha256_file(source) != expected_hash or sha256_file(retained) != expected_hash:
        raise RuntimeError("Hash changed before quarantine.")

    if target.exists():
        raise RuntimeError(f"Quarantine collision: {target}")

    shutil.move(str(source), str(target))

    if not retained.exists() or sha256_file(retained) != expected_hash:
        raise RuntimeError("Retained canonical copy failed verification after quarantine.")

    con.execute("""
      INSERT INTO quarantine_manifest(
        run_id,created_at,source_path,quarantine_path,retained_path,size,sha256,verified
      ) VALUES (?,?,?,?,?,?,?,1)
    """, (run_id, utcnow(), str(source), str(target), str(retained), target.stat().st_size, expected_hash))
    con.commit()
    return target

def run_once():
    policy = load_policy()
    con = init_db()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    con.execute("INSERT INTO runs(run_id,started_at,status) VALUES (?,?,?)", (run_id, utcnow(), "RUNNING"))
    con.commit()

    min_size = int(policy["min_hash_size_mb"]) * 1024 * 1024
    size_groups = defaultdict(list)
    files_seen = 0
    bytes_seen = 0

    drives = fixed_drives()
    drives = [d for d in drives if d[:1].upper() not in {x.upper() for x in policy.get("exclude_drive_letters", [])}]

    for drive in drives:
        for path, size, mtime in walk_drive(Path(drive), policy):
            files_seen += 1
            bytes_seen += size
            if size >= min_size:
                size_groups[size].append({"path": str(path), "size": size, "mtime": mtime})

    dup_groups = 0
    q_count = 0
    q_bytes = 0
    review = 0

    for size, candidates in size_groups.items():
        if len(candidates) < 2:
            continue
        by_hash = defaultdict(list)
        for item in candidates:
            try:
                item["sha256"] = sha256_file(Path(item["path"]))
                by_hash[item["sha256"]].append(item)
            except Exception as e:
                review += 1
                add_review(con, run_id, "HASH_FAILED", item["path"], {"error": repr(e)})
        for digest, items in by_hash.items():
            if len(items) < 2:
                continue
            dup_groups += 1
            canonical = choose_canonical(items, policy)
            if canonical is None:
                review += 1
                add_review(con, run_id, "CANONICAL_AMBIGUOUS", items[0]["path"], {"group": items})
                continue

            for item in items:
                if item["path"] == canonical["path"]:
                    continue
                src = Path(item["path"])

                # Never auto-move protected/runtime trees or system-like paths.
                if protected_tree(src, policy) or excluded(src, policy):
                    review += 1
                    add_review(con, run_id, "PROTECTED_DUPLICATE", str(src), {
                        "retained": canonical["path"], "sha256": digest, "size": size
                    })
                    continue

                # Only auto-quarantine lower-priority copies.
                if priority(item["path"], policy) <= priority(canonical["path"], policy):
                    review += 1
                    add_review(con, run_id, "EQUAL_OR_HIGHER_PRIORITY_COPY", str(src), {
                        "retained": canonical["path"], "sha256": digest, "size": size
                    })
                    continue

                if not policy.get("quarantine_enabled", True):
                    continue

                try:
                    safe_quarantine(src, Path(canonical["path"]), digest, run_id, policy, con)
                    q_count += 1
                    q_bytes += size
                except Exception as e:
                    review += 1
                    add_review(con, run_id, "QUARANTINE_FAILED", str(src), {
                        "retained": canonical["path"], "sha256": digest, "size": size, "error": repr(e)
                    })

    con.execute("""
      UPDATE runs SET completed_at=?, status='COMPLETED', files_seen=?, bytes_seen=?,
      duplicate_groups=?, quarantined_files=?, quarantined_bytes=?, review_items=?
      WHERE run_id=?
    """, (utcnow(), files_seen, bytes_seen, dup_groups, q_count, q_bytes, review, run_id))
    con.commit()

    report = {
        "run_id": run_id,
        "drives": drives,
        "files_seen": files_seen,
        "bytes_seen": bytes_seen,
        "duplicate_groups": dup_groups,
        "quarantined_files": q_count,
        "quarantined_bytes": q_bytes,
        "review_items": review,
        "database": str(DB),
        "quarantine_enabled": policy.get("quarantine_enabled", True),
        "permanent_delete_enabled": False
    }
    report_path = REPORTS / f"autopilot_{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Run one maintenance cycle")
    ap.add_argument("--loop", action="store_true", help="Run continuously")
    ap.add_argument("--hours", type=float, default=24, help="Hours between runs in loop mode")
    args = ap.parse_args()

    if args.loop:
        while True:
            try:
                run_once()
            except Exception as e:
                print(f"AUTOPILOT ERROR: {e!r}", file=sys.stderr)
            time.sleep(max(1, int(args.hours * 3600)))
    else:
        run_once()

if __name__ == "__main__":
    main()
