param(
    [ValidateSet('Api', 'Web', 'Seed')]
    [string]$Mode = 'Api',
    [string]$PythonExe = '',
    [int]$ApiPort = 8793,
    [int]$WebPort = 5193
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if ($Mode -eq 'Web') {
        $env:POSTERPILOT_API_TARGET = "http://127.0.0.1:$ApiPort"
        $env:VITE_POSTERPILOT_DEMO = 'true'
        & npm.cmd --prefix apps/web run dev -- --host 127.0.0.1 --port $WebPort --strictPort
    } else {
        if (-not $PythonExe) {
            $localPython = Join-Path $root '.venv/Scripts/python.exe'
            if (Test-Path -LiteralPath $localPython) {
                $PythonExe = $localPython
            } else {
                $PythonExe = (Get-Command python -ErrorAction Stop).Source
            }
        }
        $env:PYTHONPATH = Join-Path $root 'apps/api'
        $env:PYTHONIOENCODING = 'utf-8'
        if ($Mode -eq 'Seed') {
            & $PythonExe scripts/verify_datahub.py --data-dir data/datahub-demo
        } else {
            & $PythonExe -m uvicorn app.datahub_demo:create_app --factory --app-dir apps/api --host 127.0.0.1 --port $ApiPort
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "DataHub command failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}
