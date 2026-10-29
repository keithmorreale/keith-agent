$ErrorActionPreference="Stop"
Copy-Item "$PSScriptRoot\rollback_quarantine.py" "C:\KeithAgent\rollback_quarantine.py" -Force
Write-Host "Rollback tool installed." -ForegroundColor Green
Write-Host 'Run: C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\rollback_quarantine.py'
