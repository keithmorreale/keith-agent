
$ErrorActionPreference = "Stop"
$Base = "C:\KeithAgent"
$Src = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path "$Base\autopilot" | Out-Null
New-Item -ItemType Directory -Force -Path "$Base\reports" | Out-Null
Copy-Item "$Src\autopilot_cleanup.py" "$Base\autopilot_cleanup.py" -Force
Copy-Item "$Src\autopilot_policy.json" "$Base\autopilot_policy.json" -Force
Write-Host ""
Write-Host "Keith Agent SAFE_AUTOPILOT v2 installed." -ForegroundColor Green
Write-Host "Run:"
Write-Host 'C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once'
