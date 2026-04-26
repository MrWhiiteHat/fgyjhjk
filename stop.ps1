# RealFake Detection Platform - Stop Script
# This script finds and terminates processes running on ports 8000 (Backend) and 3000 (Frontend).

Write-Host "🛑 Stopping RealFake Detection Platform..." -ForegroundColor Magenta

$ports = @(8000, 3000)

foreach ($port in $ports) {
    Write-Host "🔍 Checking port $port..." -ForegroundColor Gray
    $procId = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
    
    if ($procId) {
        $procName = Get-Process -Id $procId | Select-Object -ExpandProperty Name
        Write-Host "   -> Found process '$procName' (PID: $procId) on port $port. Terminating..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force
        Write-Host "   ✅ Port $port cleared." -ForegroundColor Green
    } else {
        Write-Host "   -> Port $port is already free." -ForegroundColor Gray
    }
}

Write-Host "`n✨ All services stopped successfully." -ForegroundColor Cyan
