param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    $backendPython = "python"
}

Write-Host "Starting backend on http://0.0.0.0:$BackendPort"
Write-Host "Starting frontend on http://0.0.0.0:$FrontendPort"
Write-Host "Press Ctrl+C to stop both jobs."

$jobs = @()
try {
    $jobs += Start-Job -Name "minimaxvidpromat-backend" -ArgumentList $backendDir, $backendPython, $BackendPort -ScriptBlock {
        param($backendDir, $backendPython, $backendPort)
        Set-Location $backendDir
        & $backendPython -m uvicorn app.main:app --host 0.0.0.0 --port $backendPort --reload
    }
    $jobs += Start-Job -Name "minimaxvidpromat-frontend" -ArgumentList $frontendDir, $FrontendPort -ScriptBlock {
        param($frontendDir, $frontendPort)
        Set-Location $frontendDir
        npm run dev -- --host 0.0.0.0 --port $frontendPort
    }

    while ($true) {
        foreach ($job in $jobs) {
            Receive-Job -Job $job
            if ($job.State -notin @("Running", "NotStarted")) {
                throw "$($job.Name) stopped with state $($job.State)"
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($job in $jobs) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}
