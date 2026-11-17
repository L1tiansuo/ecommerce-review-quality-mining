# API latency benchmark: hit each endpoint N times, report P50 / P95 / P99.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\bench_api.ps1 -N 200
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as ANSI,
#       and non-ASCII characters break parsing (same bug as run_all.ps1).
param(
    [int]$N = 200,
    [int]$Warm = 20,
    [switch]$Refresh,
    [string]$Base = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::DefaultConnectionLimit = 64

$login = @{ username = "admin"; password = "QrDemo2026!"; captcha = "2026" } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri "$Base/api/v1/auth/login" -Method Post -Body $login `
        -ContentType "application/json" -TimeoutSec 30).data.token
$headers = @{ Authorization = "Bearer $token" }

function Get-Percentile {
    param($sorted, [double]$p)
    $i = [int][Math]::Min($sorted.Count - 1, [Math]::Ceiling($p * $sorted.Count) - 1)
    return [math]::Round($sorted[$i], 1)
}

function Measure-Endpoint {
    param([string]$Name, [string]$Url)
    $times = New-Object System.Collections.Generic.List[double]
    # warm-up: drop first-connection and JIT effects
    for ($i = 0; $i -lt $Warm; $i++) { Invoke-RestMethod -Uri $Url -Headers $headers -TimeoutSec 60 | Out-Null }
    for ($i = 0; $i -lt $N; $i++) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        Invoke-RestMethod -Uri $Url -Headers $headers -TimeoutSec 60 | Out-Null
        $sw.Stop()
        $times.Add($sw.Elapsed.TotalMilliseconds)
    }
    $sorted = @($times | Sort-Object)
    [pscustomobject]@{
        endpoint = $Name
        count    = $sorted.Count
        p50_ms   = Get-Percentile $sorted 0.50
        p95_ms   = Get-Percentile $sorted 0.95
        p99_ms   = Get-Percentile $sorted 0.99
        max_ms   = [math]::Round($sorted[-1], 1)
    }
}

$dashUrl = "$Base/api/v1/dashboard/overview"
$dashName = "dashboard/overview"
if ($Refresh) { $dashUrl = "$dashUrl`?refresh=true"; $dashName = "dashboard/overview?refresh=true" }
$result = @(
    Measure-Endpoint $dashName $dashUrl
    Measure-Endpoint "products/68382/profile" "$Base/api/v1/products/68382/profile"
    Measure-Endpoint "alerts?page=1" "$Base/api/v1/alerts?page=1"
)
$result | Format-Table -AutoSize
$outName = if ($Refresh) { "bench-mysql-refresh.json" } else { "bench-mysql.json" }
$result | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 "$PSScriptRoot\..\docs\$outName"
Write-Host "written docs\$outName"
