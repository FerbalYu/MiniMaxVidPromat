$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Push-Location $backendDir
try {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created backend\.env. Fill MINIMAX_API_KEY before real video analysis."
    }
}
finally {
    Pop-Location
}

Push-Location $frontendDir
try {
    npm install
    npx playwright install chromium
    if (-not (Test-Path ".env.local")) {
        Copy-Item ".env.example" ".env.local"
    }
}
finally {
    Pop-Location
}

Write-Host "Setup finished. Run .\scripts\dev.ps1 for development or .\scripts\start.ps1 for same-origin local serving."
