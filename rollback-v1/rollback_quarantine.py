from __future__ import annotations
import hashlib, shutil, sqlite3, threading, time
from datetime import datetime
from pathlib import Path

BASE=Path(r"C:\KeithAgent")
DB=BASE/"autopilot"/"autopilot.db"
REPORTS=BASE/"reports"
lock=threading.Lock()
S={"total":0,"done":0,"restored":0,"skipped":0,"errors":0,"current":"","start":time.monotonic(),"last":time.monotonic(),"finished":False}

def hfile(p):
    h=hashlib.sha256()
    with open(p,"rb",buffering=0) as f:
        while True:
            b=f.read(8*1024*1024)
            if not b: break
            h.update(b)
            with lock:
                S["current"]=str(p); S["last"]=time.monotonic()
    return h.hexdigest().upper()

def beat():
    while True:
        with lock: s=dict(S)
        e=int(time.monotonic()-s["start"]); idle=int(time.monotonic()-s["last"])
        hh,r=divmod(e,3600); mm,ss=divmod(r,60)
        pct=(100*s["done"]/s["total"]) if s["total"] else 0
        print(f"[{hh:02d}:{mm:02d}:{ss:02d}] ROLLBACK | {s['done']}/{s['total']} ({pct:.1f}%) | Restored {s['restored']} | Skipped {s['skipped']} | Errors {s['errors']} | Idle {idle}s",flush=True)
        if s["current"]: print(f"    Current: {s['current']}",flush=True)
        if s["finished"]: return
        time.sleep(5)

def main():
    REPORTS.mkdir(parents=True,exist_ok=True)
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    rows=c.execute("""SELECT id,run_id,source_path,quarantine_path,retained_path,size,sha256,verified
                      FROM quarantine_manifest WHERE verified=1 ORDER BY id DESC""").fetchall()
    with lock:
        S["total"]=len(rows); S["start"]=time.monotonic(); S["last"]=time.monotonic()
    threading.Thread(target=beat,daemon=True).start()
    logp=REPORTS/f"autopilot_rollback_{datetime.now():%Y%m%d_%H%M%S}.log"
    def log(x):
        with open(logp,"a",encoding="utf-8") as f: f.write(x+"\n")

    for r in rows:
        src=Path(r["source_path"]); q=Path(r["quarantine_path"]); exp=(r["sha256"] or "").upper()
        with lock:
            S["current"]=str(q); S["last"]=time.monotonic()
        try:
            if src.exists():
                log(f"SKIP source exists | {src} | quarantine={q}")
                with lock: S["skipped"]+=1; S["done"]+=1; S["last"]=time.monotonic()
                continue
            if not q.exists():
                log(f"ERROR quarantine missing | source={src} | quarantine={q}")
                with lock: S["errors"]+=1; S["done"]+=1; S["last"]=time.monotonic()
                continue
            if exp and hfile(q)!=exp:
                raise RuntimeError("Quarantine SHA256 mismatch")
            src.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(q),str(src))
            if not src.exists(): raise RuntimeError("Restore target missing after move")
            if exp and hfile(src)!=exp: raise RuntimeError("Restored SHA256 mismatch")
            log(f"RESTORED | {q} -> {src}")
            with lock: S["restored"]+=1; S["done"]+=1; S["last"]=time.monotonic()
        except Exception as e:
            log(f"ERROR | source={src} | quarantine={q} | {e!r}")
            with lock: S["errors"]+=1; S["done"]+=1; S["last"]=time.monotonic()

    with lock:
        S["finished"]=True; final=dict(S)
    print("\n"+"="*70)
    print("KEITH AGENT QUARANTINE ROLLBACK COMPLETE")
    print(f"Manifest rows: {final['total']}")
    print(f"Restored:      {final['restored']}")
    print(f"Skipped:       {final['skipped']}")
    print(f"Errors:        {final['errors']}")
    print(f"Log:           {logp}")
    print("="*70,flush=True)

if __name__=="__main__": main()
