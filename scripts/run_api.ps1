param(
    [int]$Port = 8787,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$apiDirectory = Join-Path $root "apps\api"

if (-not (Test-Path $python)) {
    throw "Python API environment is missing. Run the API installation command first."
}

$arguments = @("-m", "uvicorn", "app.main:app", "--app-dir", $apiDirectory, "--host", "127.0.0.1", "--port", $Port)
if ($Reload) {
    $arguments += "--reload"
}

& $python @arguments
