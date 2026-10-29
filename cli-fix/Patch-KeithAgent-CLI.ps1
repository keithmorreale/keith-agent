$ErrorActionPreference = "Stop"

$Source = Join-Path $PSScriptRoot "KeithAgent.ps1"
$Dest = "C:\KeithAgent\bin\KeithAgent.ps1"

if (-not (Test-Path $Source)) {
    throw "Missing replacement CLI: $Source"
}
if (-not (Test-Path (Split-Path $Dest -Parent))) {
    throw "Keith Agent bin folder not found."
}

if (Test-Path $Dest) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item $Dest "$Dest.backup_$stamp" -Force
}

Copy-Item $Source $Dest -Force

Write-Host "KeithAgent CLI patched." -ForegroundColor Green
Write-Host ""
Write-Host "Testing status command..." -ForegroundColor Cyan
& "C:\KeithAgent\bin\KeithAgent.cmd" status

Write-Host ""
Write-Host "Patch complete." -ForegroundColor Green
Write-Host 'Next test: KeithAgent list "D:\08_EDUCATION"'
