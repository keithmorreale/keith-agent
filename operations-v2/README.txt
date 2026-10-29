Keith Agent Operations Automation v2

1. Extract the entire ZIP folder.
2. Open Administrator PowerShell.
3. Run:

   Set-ExecutionPolicy -Scope Process Bypass
   & "P:\KeithAgent_Operations_Automation_v2\Install-KeithAgent-Operations-v2.ps1"

Installed commands:

   KeithAgent status
   KeithAgent list "D:\08_EDUCATION"
   KeithAgent scan "D:\02_PROJECTS"
   KeithAgent jobs

Also installs:
- Daily secure Keith Agent backup at 3:15 AM
- Watchdog every 5 minutes
- Job-history retention at 3:30 AM
