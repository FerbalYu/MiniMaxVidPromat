$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$results = [ordered]@{}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "==> $Name"
    try {
        & $Command
        $results[$Name] = "passed"
    }
    catch {
        $results[$Name] = "failed: $($_.Exception.Message)"
        throw
    }
}

Invoke-Step "frontend build" {
    Push-Location (Join-Path $root "frontend")
    try {
        npm run build
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend compile" {
    Push-Location (Join-Path $root "backend")
    try {
        python -m compileall app
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend import" {
    Push-Location (Join-Path $root "backend")
    try {
        python -c "from app.main import app; print(app.title)"
    }
    finally {
        Pop-Location
    }
}

$reportDir = Join-Path $root ".evolution"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportPath = Join-Path $reportDir "last-eval.json"
$payload = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    status = "passed"
    results = $results
}
$payload | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $reportPath
Write-Host "Eval passed. Report: $reportPath"

