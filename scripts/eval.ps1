$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$results = [ordered]@{}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE"
    }
}

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
        Invoke-Native npm run build
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "frontend e2e" {
    Push-Location (Join-Path $root "frontend")
    try {
        Invoke-Native npx playwright test
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend compile" {
    Push-Location (Join-Path $root "backend")
    try {
        Invoke-Native python -m compileall app
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend import" {
    Push-Location (Join-Path $root "backend")
    try {
        Invoke-Native python -c "from app.main import app; print(app.title)"
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend smoke" {
    Push-Location (Join-Path $root "backend")
    try {
        Invoke-Native python tests/smoke_api.py
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "powershell syntax" {
    Get-ChildItem -Path (Join-Path $root "scripts") -Filter "*.ps1" | ForEach-Object {
        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors) | Out-Null
        if ($errors.Count -gt 0) {
            throw "$($_.Name) has PowerShell syntax errors: $($errors[0].Message)"
        }
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
