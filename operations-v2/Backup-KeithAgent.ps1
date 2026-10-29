$ErrorActionPreference = "Stop"

$SourceRoot = "C:\KeithAgent"
$BackupRoot = "D:\10_ARCHIVES\KeithAgent_Automated_Backups"

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$temp = Join-Path $env:TEMP "KeithAgentBackup_$stamp"
New-Item -ItemType Directory -Path $temp -Force | Out-Null

try {
    $files = @(
        "C:\KeithAgent\data\keith-agent.db",
        "C:\KeithAgent\.env",
        "C:\KeithAgent\coordinator.env",
        "C:\KeithAgent\coordinator\main.py",
        "C:\KeithAgent\worker\worker.py",
        "C:\KeithAgent\Status-KeithAgent.ps1"
    )

    foreach ($file in $files) {
        if (Test-Path $file) {
            $rel = $file.Substring($SourceRoot.Length).TrimStart('\')
            $dest = Join-Path $temp $rel
            $parent = Split-Path $dest -Parent
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            Copy-Item $file $dest -Force
        }
    }

    $zip = Join-Path $BackupRoot "KeithAgent_Backup_$stamp.zip"
    Compress-Archive `
        -Path "$temp\*" `
        -DestinationPath $zip `
        -CompressionLevel Optimal `
        -Force

    $hash = Get-FileHash $zip -Algorithm SHA256

    Write-Host "Backup: $zip"
    Write-Host "SHA256: $($hash.Hash)"

    Get-ChildItem $BackupRoot -Filter "KeithAgent_Backup_*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 14 |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
finally {
    if (Test-Path $temp) {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
