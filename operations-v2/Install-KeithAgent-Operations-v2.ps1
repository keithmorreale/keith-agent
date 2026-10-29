param(
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$Root = "C:\KeithAgent"
$Bin = Join-Path $Root "bin"
$Ops = Join-Path $Root "operations"
$BundleDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Keith Agent Operations Automation Installer v2 ===" -ForegroundColor Cyan

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)

if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an Administrator PowerShell."
}

foreach ($p in @($Bin,$Ops,"D:\10_ARCHIVES\KeithAgent_Automated_Backups")) {
    New-Item -ItemType Directory -Path $p -Force | Out-Null
}

$required = @(
    "KeithAgent.ps1",
    "Backup-KeithAgent.ps1",
    "Watchdog-KeithAgent.ps1",
    "Prune-KeithAgentJobs.ps1"
)

foreach ($name in $required) {
    $src = Join-Path $BundleDir $name
    if (-not (Test-Path $src)) {
        throw "Missing bundle file: $src"
    }
}

Copy-Item (Join-Path $BundleDir "KeithAgent.ps1") `
    (Join-Path $Bin "KeithAgent.ps1") -Force

Copy-Item (Join-Path $BundleDir "Backup-KeithAgent.ps1") `
    (Join-Path $Ops "Backup-KeithAgent.ps1") -Force

Copy-Item (Join-Path $BundleDir "Watchdog-KeithAgent.ps1") `
    (Join-Path $Ops "Watchdog-KeithAgent.ps1") -Force

Copy-Item (Join-Path $BundleDir "Prune-KeithAgentJobs.ps1") `
    (Join-Path $Ops "Prune-KeithAgentJobs.ps1") -Force

$cmdPath = Join-Path $Bin "KeithAgent.cmd"

@"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\KeithAgent\bin\KeithAgent.ps1" %*
"@ | Set-Content $cmdPath -Encoding ASCII

$machinePath = [Environment]::GetEnvironmentVariable("Path","Machine")

if (($machinePath -split ';') -notcontains $Bin) {
    $newPath = $machinePath.TrimEnd(';') + ";" + $Bin
    [Environment]::SetEnvironmentVariable("Path",$newPath,"Machine")
    Write-Host "Added $Bin to machine PATH." -ForegroundColor Green
}
else {
    Write-Host "$Bin is already in the machine PATH." -ForegroundColor Yellow
}

if (($env:Path -split ';') -notcontains $Bin) {
    $env:Path += ";$Bin"
}

$BackupRoot = "D:\10_ARCHIVES\KeithAgent_Automated_Backups"
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

& icacls.exe $BackupRoot /inheritance:r | Out-Null
& icacls.exe $BackupRoot /grant:r `
    "${currentUser}:(OI)(CI)F" `
    "SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" | Out-Null

$backupPath = Join-Path $Ops "Backup-KeithAgent.ps1"
$watchdogPath = Join-Path $Ops "Watchdog-KeithAgent.ps1"
$prunePath = Join-Path $Ops "Prune-KeithAgentJobs.ps1"

$systemPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

$backupAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupPath`""

$backupTrigger = New-ScheduledTaskTrigger -Daily -At 3:15am

Register-ScheduledTask `
    -TaskName "Keith Agent Daily Backup" `
    -Action $backupAction `
    -Trigger $backupTrigger `
    -Principal $systemPrincipal `
    -Settings $settings `
    -Force | Out-Null

$watchAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$watchdogPath`""

$watchTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "Keith Agent Watchdog" `
    -Action $watchAction `
    -Trigger $watchTrigger `
    -Principal $systemPrincipal `
    -Settings $settings `
    -Force | Out-Null

$pruneAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$prunePath`" -RetentionDays $RetentionDays"

$pruneTrigger = New-ScheduledTaskTrigger -Daily -At 3:30am

Register-ScheduledTask `
    -TaskName "Keith Agent Job Retention" `
    -Action $pruneAction `
    -Trigger $pruneTrigger `
    -Principal $systemPrincipal `
    -Settings $settings `
    -Force | Out-Null

Write-Host ""
Write-Host "Creating initial secure backup..." -ForegroundColor Cyan
& powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $backupPath

Write-Host ""
Write-Host "Testing KeithAgent status command..." -ForegroundColor Cyan
& (Join-Path $Bin "KeithAgent.cmd") status

Write-Host ""
Write-Host "Scheduled tasks:" -ForegroundColor Green

Get-ScheduledTask `
    -TaskName "Keith Agent Daily Backup","Keith Agent Watchdog","Keith Agent Job Retention" |
    Select-Object TaskName,State |
    Format-Table -AutoSize

Write-Host ""
Write-Host "INSTALL COMPLETE." -ForegroundColor Green
Write-Host ""
Write-Host "Available commands:"
Write-Host '  KeithAgent status'
Write-Host '  KeithAgent list "D:\08_EDUCATION"'
Write-Host '  KeithAgent scan "D:\02_PROJECTS"'
Write-Host '  KeithAgent jobs'

