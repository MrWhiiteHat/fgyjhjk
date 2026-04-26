$ErrorActionPreference = "Stop"

$scriptsRoot = Resolve-Path $PSScriptRoot
$backendScript = Join-Path $scriptsRoot "run_backend.ps1"
$frontendScript = Join-Path $scriptsRoot "run_frontend.ps1"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $backendScript
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $frontendScript

Write-Host "Started backend and frontend in separate PowerShell windows."
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
