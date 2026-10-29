$ErrorActionPreference = "Continue"

$log = "C:\KeithAgent\logs\watchdog.log"
New-Item -ItemType Directory -Path (Split-Path $log -Parent) -Force | Out-Null

function Write-WatchdogLog {
    param([string]$Message)
    "$(Get-Date -Format o) $Message" | Add-Content $log
}

$coordHealthy = $false

try {
    $health = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8765/health" `
        -TimeoutSec 5

    if ($health.status -eq "ok") {
        $coordHealthy = $true
    }
}
catch {}

if (-not $coordHealthy) {
    Write-WatchdogLog "Coordinator unhealthy; restarting scheduled task."
    Stop-ScheduledTask `
        -TaskName "Keith Agent Coordinator" `
        -ErrorAction SilentlyContinue

    Start-Sleep -Seconds 1

    Start-ScheduledTask `
        -TaskName "Keith Agent Coordinator" `
        -ErrorAction SilentlyContinue
}

$worker = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match 'C:\\KeithAgent\\worker\\worker.py'
    }

if (-not $worker) {
    Write-WatchdogLog "Worker missing; restarting scheduled task."

    Start-ScheduledTask `
        -TaskName "Keith Agent Worker" `
        -ErrorAction SilentlyContinue
}
