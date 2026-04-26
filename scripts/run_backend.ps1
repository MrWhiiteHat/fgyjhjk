param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found at $pythonExe. Create it first with: python -m venv .venv"
}

$args = @("-m", "uvicorn", "app.backend.main:app", "--host", $BindHost, "--port", "$Port")
if ($Reload.IsPresent) {
    $args += "--reload"
}

& $pythonExe @args
