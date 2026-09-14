$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force $logs | Out-Null

Push-Location $root
try {
    docker compose -f infra\docker-compose.yml up -d ollama chroma

    $api = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $root "scripts\run_api.ps1")
    ) -RedirectStandardOutput (Join-Path $logs "api.out.log") -RedirectStandardError (Join-Path $logs "api.err.log")

    $deepgaze = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $root "scripts\run_deepgaze.ps1")
    ) -RedirectStandardOutput (Join-Path $logs "deepgaze.out.log") -RedirectStandardError (Join-Path $logs "deepgaze.err.log")

    $web = Start-Process npm.cmd -WindowStyle Hidden -PassThru -ArgumentList @("run", "dev:web") `
        -RedirectStandardOutput (Join-Path $logs "web.out.log") -RedirectStandardError (Join-Path $logs "web.err.log")

    Write-Host "PosterPilot started. Web: http://127.0.0.1:5173  API: http://127.0.0.1:8787"
    Write-Host "Process IDs: API=$($api.Id) DeepGaze=$($deepgaze.Id) Web=$($web.Id)"
} finally {
    Pop-Location
}
