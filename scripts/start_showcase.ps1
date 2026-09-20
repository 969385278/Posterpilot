param(
    [ValidateSet('Api', 'Web', 'Seed')]
    [string]$Mode = 'Api',
    [string]$PythonExe = '',
    [int]$ApiPort = 8794,
    [int]$WebPort = 5194
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if ($Mode -eq 'Web') {
        $env:POSTERPILOT_API_TARGET = "http://127.0.0.1:$ApiPort"
        $env:VITE_POSTERPILOT_DEMO = 'true'
        $env:VITE_POSTERPILOT_SHOWCASE = 'true'
        & npm.cmd --prefix apps/web run dev -- --host 127.0.0.1 --port $WebPort --strictPort
    } else {
        if (-not $PythonExe) {
            $localPython = Join-Path $root '.venv/Scripts/python.exe'
            if (Test-Path -LiteralPath $localPython) { $PythonExe = $localPython }
            else { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
        }
        $env:PYTHONPATH = Join-Path $root 'apps/api'
        $env:PYTHONIOENCODING = 'utf-8'
        if ($Mode -eq 'Seed') {
            & $PythonExe scripts/prepare_showcase.py
        } else {
            & $PythonExe -m uvicorn app.showcase:create_app --factory --app-dir apps/api --host 127.0.0.1 --port $ApiPort
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "Showcase command failed (exit $LASTEXITCODE)." }
} finally { Pop-Location }
