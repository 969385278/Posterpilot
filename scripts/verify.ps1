$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    & ".\.venv\Scripts\python.exe" -m pytest apps\api\tests -q
    if ($LASTEXITCODE -ne 0) { throw "API tests failed with exit code $LASTEXITCODE" }
    & ".\.venv\Scripts\python.exe" -m ruff check apps\api scripts
    if ($LASTEXITCODE -ne 0) { throw "API Ruff check failed with exit code $LASTEXITCODE" }
    & ".\.venv-deepgaze\Scripts\python.exe" -m pytest services\deepgaze\tests -q
    if ($LASTEXITCODE -ne 0) { throw "DeepGaze tests failed with exit code $LASTEXITCODE" }
    & ".\.venv-deepgaze\Scripts\python.exe" -m ruff check services\deepgaze
    if ($LASTEXITCODE -ne 0) { throw "DeepGaze Ruff check failed with exit code $LASTEXITCODE" }
    npm run test:web
    if ($LASTEXITCODE -ne 0) { throw "Web tests failed with exit code $LASTEXITCODE" }
    npm run build:web
    if ($LASTEXITCODE -ne 0) { throw "Web build failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
