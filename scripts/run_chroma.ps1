param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$chromaExe = Join-Path $root '.venv/Scripts/chroma.exe'
$storage = Join-Path $root 'data/chroma-runtime'
if (-not (Test-Path -LiteralPath $chromaExe)) {
    throw 'Install the API dependencies into .venv before starting Chroma.'
}

& $chromaExe run --path $storage --host 127.0.0.1 --port $Port
if ($LASTEXITCODE -ne 0) { throw "Chroma exited with code $LASTEXITCODE." }
