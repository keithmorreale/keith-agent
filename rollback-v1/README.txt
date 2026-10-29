Keith Agent Quarantine Rollback v1

Restores all verified quarantine_manifest entries from C:\KeithAgent\autopilot\autopilot.db.
It never overwrites an existing original path, verifies SHA-256 before and after each restore,
prints a heartbeat every 5 seconds, and writes a detailed log under C:\KeithAgent\reports.

Install:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_rollback.ps1

Run:
C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\rollback_quarantine.py
