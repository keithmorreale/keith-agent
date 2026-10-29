Keith Agent SAFE_AUTOPILOT v3

Key safety changes:
- Scans all fixed drives.
- System areas are excluded.
- Unreal projects, engines, Ren'Py builds/projects, Steam libraries, ComfyUI,
  Python/Conda environments, backups, recovered-data trees, Git repos, and
  application/runtime trees are inventory-only.
- Protected file types such as .uasset, .umap, .uproject, .dll, .exe, .sys,
  VM disks, and ISOs are never automatically quarantined.
- Automatic duplicate quarantine is limited to approved user-data zones:
  00_INBOX, 04_BUSINESS, 05_LEGAL, 06_FINANCE, 07_FAMILY, 08_EDUCATION,
  10_ARCHIVES, and 12_MEDIA.
- Ambiguous or protected duplicate groups go to the review queue.
- Permanent deletion remains disabled.
- Live heartbeat every 5 seconds.

Install:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_autopilot_v3.ps1

Run:
C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once
