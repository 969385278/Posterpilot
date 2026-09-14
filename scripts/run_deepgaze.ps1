param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv-deepgaze\Scripts\python.exe"
$serviceDirectory = Join-Path $root "services\deepgaze"

if (-not (Test-Path $python)) {
    throw "DeepGaze environment is missing. Create .venv-deepgaze and install services/deepgaze/requirements-model.txt first."
}

& $python -m uvicorn app.main:app --app-dir $serviceDirectory --host 127.0.0.1 --port $Port
