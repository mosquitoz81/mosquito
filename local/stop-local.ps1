# stop-local.ps1 - Stop all Pockie Ninja offline services
# Run from the project root: .\local\stop-local.ps1

$ErrorActionPreference = "Continue"

function Write-Status($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] OK: $msg" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Pockie Ninja Offline Server - Stopping    " -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

# Stop Python processes (web server, proxy, policy server)
$pythonProcs = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq 'python.exe' -and (
        $_.CommandLine -match 'local_web\.py' -or
        $_.CommandLine -match 'socket_proxy\.py' -or
        $_.CommandLine -match 'flash_policy\.py'
    )}

foreach ($p in $pythonProcs) {
    Write-Status "Stopping $($p.Name) (PID $($p.ProcessId)): $($p.CommandLine)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Ok "Stopped PID $($p.ProcessId)"
}

# Stop DmEnter
$dmProcs = Get-Process -Name "DmEnter" -ErrorAction SilentlyContinue
foreach ($p in $dmProcs) {
    Write-Status "Stopping DmEnter (PID $($p.Id))"
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Write-Ok "Stopped DmEnter PID $($p.Id)"
}

# Stop Java game server (careful: only stop game-related Java)
$javaProcs = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq 'java.exe' -and $_.CommandLine -match 'game|Pockie|app.bin' }

foreach ($p in $javaProcs) {
    Write-Status "Stopping Java game server (PID $($p.ProcessId)): $($p.CommandLine)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Ok "Stopped Java PID $($p.ProcessId)"
}

Write-Host ""
Write-Ok "All game services stopped."
Write-Host ""
Write-Host "  Note: MySQL is NOT stopped (may be used by other apps)" -ForegroundColor Gray
Write-Host "  To stop MySQL: net stop mysql  or  use XAMPP control panel" -ForegroundColor Gray
Write-Host ""
