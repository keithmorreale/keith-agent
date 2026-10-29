param(
    [Parameter(Position=0,Mandatory=$true)]
    [ValidateSet("list","scan","status","jobs","raw")]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$Path,

    [Parameter(Position=2)]
    [string]$RawPath
)

$ErrorActionPreference = "Stop"
$Coordinator = "http://127.0.0.1:8765"
$EnvFile = "C:\KeithAgent\coordinator.env"

function Get-AdminToken {
    if (-not (Test-Path $EnvFile)) {
        throw "Coordinator env not found: $EnvFile"
    }

    $token = Get-Content $EnvFile |
        Where-Object { $_ -match '^KEITH_AGENT_ADMIN_TOKEN=' } |
        ForEach-Object { $_.Split('=',2)[1].Trim() } |
        Select-Object -First 1

    if (-not $token) {
        throw "KEITH_AGENT_ADMIN_TOKEN not found in $EnvFile"
    }

    return $token
}

function Get-Headers {
    return @{
        Authorization = "Bearer $(Get-AdminToken)"
        "Content-Type" = "application/json"
    }
}

function Submit-Job {
    param(
        [Parameter(Mandatory=$true)][string]$Action,
        [Parameter(Mandatory=$true)][hashtable]$Arguments
    )

    $headers = Get-Headers

    $body = @{
        worker_id = "pc1"
        action = $Action
        arguments = $Arguments
    } | ConvertTo-Json -Depth 10

    $created = Invoke-RestMethod `
        -Uri "$Coordinator/admin/jobs" `
        -Method Post `
        -Headers $headers `
        -Body $body

    Write-Host "Queued job $($created.job_id)" -ForegroundColor Cyan

    $deadline = (Get-Date).AddSeconds(60)
    $job = $null

    do {
        Start-Sleep -Milliseconds 750

        $jobs = @(
            Invoke-RestMethod `
                -Uri "$Coordinator/admin/jobs" `
                -Method Get `
                -Headers $headers
        )

        $job = $jobs |
            Where-Object { $_.job_id -eq $created.job_id } |
            Select-Object -First 1

        if ($job -and $job.status -in @("completed","failed")) {
            break
        }
    }
    while ((Get-Date) -lt $deadline)

    if (-not $job) {
        throw "Could not retrieve job $($created.job_id)."
    }

    if ($job.status -eq "failed") {
        Write-Host "FAILED: $($job.error)" -ForegroundColor Red
        exit 1
    }

    if ($job.status -ne "completed") {
        Write-Host "Job is still $($job.status)." -ForegroundColor Yellow
        return
    }

    if ($job.result) {
        try {
            $obj = $job.result | ConvertFrom-Json
            $obj | ConvertTo-Json -Depth 20
        }
        catch {
            $job.result
        }
    }
    else {
        Write-Host "Completed." -ForegroundColor Green
    }
}

switch ($Command) {
    "status" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass `
            -File "C:\KeithAgent\Status-KeithAgent.ps1"
    }

    "jobs" {
        Invoke-RestMethod `
            -Uri "$Coordinator/admin/jobs" `
            -Method Get `
            -Headers (Get-Headers) |
            ConvertTo-Json -Depth 20
    }

    "list" {
        if (-not $Path) {
            throw 'Usage: KeithAgent list "D:\path"'
        }

        Submit-Job -Action "list" -Arguments @{ path = $Path }
    }

    "scan" {
        if (-not $Path) {
            throw 'Usage: KeithAgent scan "D:\path"'
        }

        Submit-Job -Action "scan_tree" -Arguments @{ path = $Path }
    }

    "raw" {
        if (-not $Path) {
            throw 'Usage: KeithAgent raw "<action>" ["<path>"]'
        }

        $args = @{}
        if ($RawPath) {
            $args.path = $RawPath
        }

        Submit-Job -Action $Path -Arguments $args
    }
}
