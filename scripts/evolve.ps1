param(
    [int]$Rounds = 3,
    [string]$Goal = "Improve MiniMaxVidPromat with autoresearch evolution"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$evolutionDir = Join-Path $root ".evolution"
$runsDir = Join-Path $evolutionDir "runs"
New-Item -ItemType Directory -Force -Path $runsDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $runsDir $timestamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$statePath = Join-Path $evolutionDir "state.json"
$promptPath = Join-Path $runDir "PROMPT.md"

$prompt = @"
# Autoresearch Run $timestamp

Goal: $Goal

Rounds: $Rounds

Follow docs/AUTORESEARCH.md:

1. Propose at least 2 candidate variants per round.
2. State the fitness hypothesis before implementing each candidate.
3. Run scripts/eval.ps1 for each candidate.
4. Write candidate reports into docs/evolution/.
5. Keep only the winning candidate for the next round.

Run directory: $runDir
"@

$prompt | Set-Content -Encoding UTF8 $promptPath

$state = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    goal = $Goal
    rounds = $Rounds
    run_dir = $runDir
    prompt = $promptPath
    next_command = ".\scripts\eval.ps1"
}
$state | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $statePath

Write-Host "Created autoresearch run:"
Write-Host $runDir
Write-Host ""
Write-Host "Prompt file:"
Write-Host $promptPath
Write-Host ""
Write-Host "Next: give PROMPT.md to the coding agent, then run .\scripts\eval.ps1 after each candidate."
