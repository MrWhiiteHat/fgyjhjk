# RealFake Detection Platform - Start Script
# This script ensures the environment is set up and starts both Backend and Frontend.

$ErrorActionPreference = "Continue"
$repoRoot = $PSScriptRoot

Write-Host "🚀 Starting RealFake Detection Platform..." -ForegroundColor Cyan

# 1. Backend Setup & Run
Write-Host "`n[1/2] Setting up Backend..." -ForegroundColor Yellow
$venvPath = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPath)) {
    Write-Host "   -> .venv not found. Creating virtual environment..." -ForegroundColor Gray
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { 
        Write-Host "   ❌ Failed to create .venv. Ensure Python is installed." -ForegroundColor Red
        exit 1
    }
}

Write-Host "   -> Ensuring backend dependencies are installed..." -ForegroundColor Gray
& $pythonExe -m pip install -r app/backend/requirements.txt | Out-Null

Write-Host "   -> Launching Backend on http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot'; .venv\Scripts\activate; uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload"

# 2. Frontend Setup & Run
Write-Host "`n[2/2] Setting up Frontend..." -ForegroundColor Yellow
$frontendDir = Join-Path $repoRoot "app\frontend"
$nodeModules = Join-Path $frontendDir "node_modules"

if (-not (Test-Path $nodeModules)) {
    Write-Host "   -> node_modules not found. Running npm install..." -ForegroundColor Gray
    Set-Location $frontendDir
    npm install
    Set-Location $repoRoot
}

Write-Host "   -> Launching Frontend on http://localhost:3000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev"

Write-Host "`n✅ Both services are starting in separate windows!" -ForegroundColor Cyan
Write-Host "   - Backend API:    http://localhost:8000/api/v1/health"
Write-Host "   - API Docs:       http://localhost:8000/docs"
Write-Host "   - Frontend UI:    http://localhost:3000"
Write-Host "`nUse 'stop.ps1' to shut down the services." -ForegroundColor Gray
