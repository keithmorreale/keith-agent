Keith Agent SAFE_AUTOPILOT v2

Adds:
- 5-second live heartbeat
- current drive/path
- elapsed time
- files and data scanned
- hash progress
- duplicate/quarantine/review counters
- persistent status JSON
- permanent deletion remains disabled

Install from PowerShell:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_autopilot_v2.ps1

Run:
C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once
