
$ErrorActionPreference = "Stop"

$Base = "C:\KeithAgent"
$Src  = Split-Path -Parent $MyInvocation.MyCommand.Path

New-Item -ItemType Directory -Force -Path "$Base\autopilot" | Out-Null
New-Item -ItemType Directory -Force -Path "$Base\reports" | Out-Null

Copy-Item "$Src\autopilot_cleanup.py" "$Base\autopilot_cleanup.py" -Force
Copy-Item "$Src\autopilot_policy.json" "$Base\autopilot_policy.json" -Force

Write-Host ""
Write-Host "Installed:"
Write-Host "  $Base\autopilot_cleanup.py"
Write-Host "  $Base\autopilot_policy.json"
Write-Host ""
Write-Host "Run one cycle with:"
Write-Host '  C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --once'
Write-Host ""
Write-Host "Continuous mode:"
Write-Host '  C:\KeithAgent\.venv\Scripts\python.exe C:\KeithAgent\autopilot_cleanup.py --loop --hours 24'
