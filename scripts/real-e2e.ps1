param(
    [Parameter(Mandatory = $true)]
    [string]$VideoPath
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    $backendPython = "python"
}

Push-Location $backendDir
try {
    & $backendPython tests/manual_real_api.py $VideoPath
    if ($LASTEXITCODE -ne 0) {
        throw "real E2E exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
