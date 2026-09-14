param(
    [string]$ApiPython,
    [string]$DeepGazePython
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $ApiPython) { $ApiPython = Join-Path $root '.venv/Scripts/python.exe' }
if (-not $DeepGazePython) { $DeepGazePython = Join-Path $root 'services/deepgaze/.venv-test/Scripts/python.exe' }
foreach ($python in @($ApiPython, $DeepGazePython)) {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Missing Python environment: $python. See docs/测试与验收入口.md."
    }
}

# Separate processes and working directories keep the two app packages isolated.
Push-Location $root
try {
    & $ApiPython -m pytest apps/api/tests -q
    if ($LASTEXITCODE -ne 0) { throw 'API tests failed.' }
} finally { Pop-Location }

Push-Location (Join-Path $root 'services/deepgaze')
try {
    & $DeepGazePython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'DeepGaze service tests failed.' }
} finally { Pop-Location }

Push-Location (Join-Path $root 'apps/web')
try {
    & npm.cmd run test -- --run
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }

Write-Output 'API tests, DeepGaze contract tests, frontend tests and build passed.'
