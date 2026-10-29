param(
    [Parameter(Position=0,Mandatory=$true)]
    [ValidateSet("list","scan","status","jobs","raw")]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$TargetPath,

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

    $line = Get-Content $EnvFile |
        Where-Object { $_ -match '^KEITH_AGENT_ADMIN_TOKEN=' } |
        Select-Object -First 1

    if (-not $line) {
        throw "KEITH_AGENT_ADMIN_TOKEN not found."
    }

    return $line.Split('=',2)[1].Trim()
}

function Get-Headers {
    @{
        Authorization = "Bearer $(Get-AdminToken)"
        "Content-Type" = "application/json"
    }
}

function Get-AllJobs {
    $response = Invoke-RestMethod `
        -Uri "$Coordinator/admin/jobs" `
        -Method Get `
        -Headers (Get-Headers)

    # Force a predictable array even for 0/1 results.
    return @($response)
}

function Find-JobById {
    param([Parameter(Mandatory=$true)][string]$JobId)

    $all = @(Get-AllJobs)

    foreach ($candidate in $all) {
        if ([string]$candidate.job_id -eq $JobId) {
            return $candidate
        }
    }

    return $null
}

function Show-Result {
    param($Job)

    if (-not $Job.result) {
        Write-Host "Completed." -ForegroundColor Green
        return
    }

    try {
        $result = $Job.result | ConvertFrom-Json
    }
    catch {
        Write-Output $Job.result
        return
    }

    # Friendlier rendering for list / scan_tree results.
    if ($null -ne $result.items) {
        Write-Host ("Path:  {0}" -f $result.path) -ForegroundColor Green
        Write-Host ("Items: {0}" -f $result.count) -ForegroundColor Green
        Write-Host ""

        $result.items |
            Select-Object name,path,is_dir,is_file,size,protected |
            Format-Table -AutoSize
        return
    }

    $result | ConvertTo-Json -Depth 30
}

function Submit-Job {
    param(
        [Parameter(Mandatory=$true)][string]$Action,
        [Parameter(Mandatory=$true)][hashtable]$Arguments
    )

    $body = @{
        worker_id = "pc1"
        action = $Action
        arguments = $Arguments
    } | ConvertTo-Json -Depth 10

    $created = Invoke-RestMethod `
        -Uri "$Coordinator/admin/jobs" `
        -Method Post `
        -Headers (Get-Headers) `
        -Body $body

    $id = [string]$created.job_id
    if (-not $id) {
        throw "Coordinator did not return a job ID."
    }

    Write-Host "Queued job $id" -ForegroundColor Cyan

    $deadline = (Get-Date).AddSeconds(120)
    $job = $null

    do {
        Start-Sleep -Milliseconds 750
        $job = Find-JobById -JobId $id

        if ($job -and ([string]$job.status -in @("completed","failed"))) {
            break
        }
    }
    while ((Get-Date) -lt $deadline)

    if (-not $job) {
        throw "Job $id was queued but could not be found in job history."
    }

    $status = [string]$job.status

    if ($status -eq "failed") {
        Write-Host "FAILED: $($job.error)" -ForegroundColor Red
        exit 1
    }

    if ($status -ne "completed") {
        Write-Host "Job $id is still '$status' after 120 seconds." -ForegroundColor Yellow
        Write-Host "Use: KeithAgent jobs"
        return
    }

    Write-Host "Completed job $id" -ForegroundColor Green
    Show-Result -Job $job
}

switch ($Command) {
    "status" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass `
            -File "C:\KeithAgent\Status-KeithAgent.ps1"
    }

    "jobs" {
        Get-AllJobs |
            Select-Object job_id,worker_id,action,status,created_at,started_at,completed_at,error |
            Format-Table -AutoSize
    }

    "list" {
        if (-not $TargetPath) {
            throw 'Usage: KeithAgent list "D:\path"'
        }

        Submit-Job -Action "list" -Arguments @{ path = $TargetPath }
    }

    "scan" {
        if (-not $TargetPath) {
            throw 'Usage: KeithAgent scan "D:\path"'
        }

        Submit-Job -Action "scan_tree" -Arguments @{ path = $TargetPath }
    }

    "raw" {
        if (-not $TargetPath) {
            throw 'Usage: KeithAgent raw "<action>" ["<path>"]'
        }

        $arguments = @{}
        if ($RawPath) {
            $arguments.path = $RawPath
        }

        Submit-Job -Action $TargetPath -Arguments $arguments
    }
}
