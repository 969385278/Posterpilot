$ErrorActionPreference = 'Stop'
$recordPath = Join-Path $PSScriptRoot '.runtime/server.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Host 'Learning app is not running.'; exit 0 }
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
$serverPath = (Resolve-Path (Join-Path $PSScriptRoot 'server.py')).Path
$processId = [int]$record.pid
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
if (-not $process) { Write-Host 'Learning app is already stopped.'; exit 0 }
$isOurs = $process.CommandLine -and $process.CommandLine.Contains($serverPath) -and ($process.Name -match '^python(w|3)?(\.exe)?$')
if (-not $isOurs) { Write-Host 'Process identity changed. Nothing was stopped.'; exit 1 }
Stop-Process -Id $processId
Write-Host 'Learning app stopped. Browser learning progress is preserved.'
