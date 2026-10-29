Keith Agent SAFE_AUTOPILOT
===========================

Purpose
-------
System-wide maintenance pass for PC1.

Current behavior:
- Discovers Windows fixed drives automatically.
- Skips common Windows/system/protected directories.
- Skips project/runtime trees with protected markers.
- Groups files >= 10 MB by size.
- SHA-256 hashes same-size candidates.
- Detects exact duplicates.
- Chooses an organized canonical copy using configured path priority.
- Moves only lower-priority exact duplicates into a per-drive quarantine tree.
- Re-verifies the retained copy after quarantine.
- Creates a SQLite review queue for ambiguous/failed cases.
- Never permanently deletes files.

Install
-------
Run install_autopilot.ps1 on PC1 from PowerShell.

One cycle:
C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once

Continuous:
C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --loop --hours 24

Safety
------
Permanent deletion is intentionally disabled.
Review database:
C:\KeithAgent\autopilot\autopilot.db

Reports:
C:\KeithAgent\reports\autopilot_*.json

Quarantine:
<drive>:\_KEITH_AGENT_QUARANTINE\<run_id>\...
