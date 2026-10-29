$ErrorActionPreference="Stop"
$Base="C:\KeithAgent"
Copy-Item "$PSScriptRoot\autopilot_cleanup.py" "$Base\autopilot_cleanup.py" -Force
Copy-Item "$PSScriptRoot\autopilot_policy.json" "$Base\autopilot_policy.json" -Force
Write-Host ""
Write-Host "Keith Agent SAFE_AUTOPILOT v3 installed." -ForegroundColor Green
Write-Host "Run one supervised cycle:"
Write-Host 'C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once'
