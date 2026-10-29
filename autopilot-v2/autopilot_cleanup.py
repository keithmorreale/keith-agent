
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, subprocess, threading, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE=Path(r"C:\KeithAgent")
REPORTS=BASE/"reports"
STATE_DIR=BASE/"autopilot"
DB=STATE_DIR/"autopilot.db"
POLICY_PATH=BASE/"autopilot_policy.json"
STATUS_PATH=STATE_DIR/"status.json"

lock=threading.Lock()
S=dict(phase="STARTING",drive="",path="",files=0,bytes=0,hashed=0,dup_groups=0,
       quarantined=0,qbytes=0,review=0,start=time.monotonic(),last=time.monotonic(),done=False)

def utc(): return datetime.now(timezone.utc).isoformat()
def fmt(n):
    x=float(n)
    for u in ("B","KB","MB","GB","TB","PB"):
        if x<1024 or u=="PB": return f"{x:.2f} {u}"
        x/=1024

def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

def status_update(**kw):
    with lock:
        S.update(kw); S["last"]=time.monotonic()

def heartbeat(pol):
    every=max(1,int(pol.get("heartbeat_seconds",5)))
    while True:
        with lock: s=dict(S)
        elapsed=int(time.monotonic()-s["start"]); idle=int(time.monotonic()-s["last"])
        h,r=divmod(elapsed,3600); m,sec=divmod(r,60)
        print(f"[{h:02d}:{m:02d}:{sec:02d}] {s['phase']} | Drive {s['drive'] or '-'} | "
              f"Files {s['files']:,} | {fmt(s['bytes'])} | Hashed {s['hashed']:,} | "
              f"Dups {s['dup_groups']:,} | Quarantine {s['quarantined']:,} | "
              f"Review {s['review']:,} | Idle {idle}s", flush=True)
        if s["path"]: print(f"    Current: {s['path']}", flush=True)
        try:
            STATUS_PATH.parent.mkdir(parents=True,exist_ok=True)
            STATUS_PATH.write_text(json.dumps({
                **{k:v for k,v in s.items() if k not in ("start","last")},
                "elapsed_seconds":elapsed,"idle_seconds":idle,"updated_at":utc()
            },indent=2),encoding="utf-8")
        except Exception: pass
        if s["done"]: return
        time.sleep(every)

def init_db():
    STATE_DIR.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS runs(
      run_id TEXT PRIMARY KEY,started_at TEXT,completed_at TEXT,status TEXT,
      files_seen INTEGER,bytes_seen INTEGER,duplicate_groups INTEGER,
      quarantined_files INTEGER,quarantined_bytes INTEGER,review_items INTEGER);
    CREATE TABLE IF NOT EXISTS review_queue(
      id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,created_at TEXT,
      reason TEXT,path TEXT,details TEXT,status TEXT DEFAULT 'OPEN');
    CREATE TABLE IF NOT EXISTS quarantine_manifest(
      id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,created_at TEXT,
      source_path TEXT,quarantine_path TEXT,retained_path TEXT,size INTEGER,
      sha256 TEXT,verified INTEGER DEFAULT 0);
    """)
    c.commit(); return c

def fixed_drives():
    p=subprocess.run(
      ["powershell","-NoProfile","-Command",
       'Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object -ExpandProperty DeviceID'],
      capture_output=True,text=True,timeout=30)
    return [x.strip()+"\\" for x in p.stdout.splitlines() if x.strip().endswith(":")]

def excluded(p,pol):
    parts={x.lower() for x in p.parts}
    return any(x.lower() in parts for x in pol["exclude_directory_names"]) or \
           p.name.lower() in {x.lower() for x in pol["exclude_file_names"]}

def protected(p,pol):
    q=str(p).lower()
    return any(x.lower() in q for x in pol["protected_markers"])

def walk(root,pol):
    stack=[root]
    while stack:
        d=stack.pop()
        status_update(phase="SCANNING",drive=root.drive,path=str(d))
        try:
            with os.scandir(d) as it:
                for e in it:
                    p=Path(e.path)
                    if excluded(p,pol): continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if not protected(p,pol): stack.append(p)
                        elif e.is_file(follow_symlinks=False):
                            st=e.stat(follow_symlinks=False)
                            with lock:
                                S["files"]+=1; S["bytes"]+=st.st_size
                                S["path"]=str(p); S["last"]=time.monotonic()
                            yield p,st.st_size
                    except OSError: pass
        except OSError: pass

def hashfile(p):
    h=hashlib.sha256()
    with open(p,"rb",buffering=0) as f:
        while True:
            b=f.read(8*1024*1024)
            if not b: break
            h.update(b)
            with lock:
                S["path"]=str(p); S["last"]=time.monotonic()
    return h.hexdigest().upper()

def score(path,pol):
    q=path.lower(); base=100
    for i,t in enumerate(pol["canonical_priority"]):
        if ("\\"+t.lower()+"\\") in q or q.endswith("\\"+t.lower()):
            base=i; break
    base += sum(100 for t in pol["low_priority_tokens"] if t.lower() in q)
    return base

def review(c,run,reason,path,details):
    c.execute("INSERT INTO review_queue(run_id,created_at,reason,path,details) VALUES(?,?,?,?,?)",
              (run,utc(),reason,path,json.dumps(details))); c.commit()
    with lock: S["review"]+=1

def run_once():
    pol=policy(); c=init_db()
    with lock:
        S.update(phase="DISCOVERING_DRIVES",drive="",path="",files=0,bytes=0,hashed=0,
                 dup_groups=0,quarantined=0,qbytes=0,review=0,start=time.monotonic(),
                 last=time.monotonic(),done=False)
    threading.Thread(target=heartbeat,args=(pol,),daemon=True).start()
    run=datetime.now().strftime("%Y%m%d_%H%M%S")
    c.execute("INSERT INTO runs(run_id,started_at,status) VALUES(?,?,?)",(run,utc(),"RUNNING")); c.commit()

    drives=fixed_drives()
    print("Fixed drives:", ", ".join(drives), flush=True)
    minimum=int(pol["min_hash_size_mb"])*1024*1024
    sizes=defaultdict(list)

    for d in drives:
        for p,n in walk(Path(d),pol):
            if n>=minimum: sizes[n].append(str(p))

    groups=[(n,paths) for n,paths in sizes.items() if len(paths)>1]
    print(f"Scan complete. Candidate size groups: {len(groups):,}", flush=True)

    for gi,(n,paths) in enumerate(groups,1):
        status_update(phase=f"HASHING {gi}/{len(groups)}",path=paths[0])
        byhash=defaultdict(list)
        for path in paths:
            try:
                h=hashfile(Path(path)); byhash[h].append(path)
                with lock: S["hashed"]+=1
            except Exception as e:
                review(c,run,"HASH_FAILED",path,{"error":repr(e)})
        for h,items in byhash.items():
            if len(items)<2: continue
            with lock: S["dup_groups"]+=1
            ranked=sorted(items,key=lambda x:(score(x,pol),x.lower()))
            if score(ranked[0],pol)>=100:
                review(c,run,"CANONICAL_AMBIGUOUS",ranked[0],{"group":items}); continue
            keep=ranked[0]
            for srcs in ranked[1:]:
                src=Path(srcs)
                if protected(src,pol) or excluded(src,pol):
                    review(c,run,"PROTECTED_DUPLICATE",srcs,{"retained":keep,"sha256":h}); continue
                if score(srcs,pol)<=score(keep,pol):
                    review(c,run,"PRIORITY_AMBIGUOUS",srcs,{"retained":keep,"sha256":h}); continue
                try:
                    status_update(phase="VERIFYING",drive=src.drive,path=srcs)
                    if hashfile(src)!=h or hashfile(Path(keep))!=h:
                        raise RuntimeError("Pre-quarantine hash verification failed")
                    qroot=Path(src.anchor)/pol["quarantine_root_name"]/run
                    rel=Path(srcs[len(src.anchor):].lstrip("\\/"))
                    target=qroot/rel
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists(): raise RuntimeError("Quarantine collision")
                    status_update(phase="QUARANTINING",drive=src.drive,path=srcs)
                    shutil.move(srcs,str(target))
                    if not Path(keep).exists() or hashfile(Path(keep))!=h:
                        raise RuntimeError("Retained copy failed post-move verification")
                    c.execute("""INSERT INTO quarantine_manifest
                      (run_id,created_at,source_path,quarantine_path,retained_path,size,sha256,verified)
                      VALUES(?,?,?,?,?,?,?,1)""",(run,utc(),srcs,str(target),keep,n,h)); c.commit()
                    with lock:
                        S["quarantined"]+=1; S["qbytes"]+=n
                except Exception as e:
                    review(c,run,"QUARANTINE_FAILED",srcs,{"retained":keep,"error":repr(e)})

    with lock:
        snap=dict(S); S["phase"]="COMPLETE"; S["done"]=True
    c.execute("""UPDATE runs SET completed_at=?,status='COMPLETED',files_seen=?,bytes_seen=?,
      duplicate_groups=?,quarantined_files=?,quarantined_bytes=?,review_items=? WHERE run_id=?""",
      (utc(),snap["files"],snap["bytes"],snap["dup_groups"],snap["quarantined"],
       snap["qbytes"],snap["review"],run)); c.commit()
    report={"run_id":run,"drives":drives,"files_seen":snap["files"],"bytes_seen":snap["bytes"],
            "duplicate_groups":snap["dup_groups"],"quarantined_files":snap["quarantined"],
            "quarantined_bytes":snap["qbytes"],"review_items":snap["review"],
            "permanent_delete_enabled":False}
    rp=REPORTS/f"autopilot_{run}.json"; rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("\n"+"="*64)
    print("KEITH AGENT MAINTENANCE COMPLETE")
    print(f"Files examined:    {snap['files']:,}")
    print(f"Data examined:     {fmt(snap['bytes'])}")
    print(f"Duplicate groups:  {snap['dup_groups']:,}")
    print(f"Quarantined files: {snap['quarantined']:,}")
    print(f"Quarantined data:  {fmt(snap['qbytes'])}")
    print(f"Needs review:      {snap['review']:,}")
    print(f"Report:            {rp}")
    print("="*64,flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--once",action="store_true")
    args=ap.parse_args()
    run_once()
