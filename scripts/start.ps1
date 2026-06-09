param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    $backendPython = "python"
}

Push-Location $frontendDir
try {
    npm run build
}
finally {
    Pop-Location
}

Push-Location $backendDir
try {
    Write-Host "Serving app at http://127.0.0.1:$Port"
    & $backendPython -m uvicorn app.main:app --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
