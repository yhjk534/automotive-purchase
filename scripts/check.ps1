$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found. Run the setup steps in README.md first."
}

Push-Location $projectRoot
try {
    $pytestTemp = Join-Path $projectRoot ".pytest_tmp"
    & $python -m pytest --basetemp $pytestTemp
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed." }

    & $python -m compileall -q src scripts
    if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

    Push-Location "frontend"
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

Write-Host "All checks passed."
