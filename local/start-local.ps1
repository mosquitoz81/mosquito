# start-local.ps1 - Start all Pockie Ninja offline services
# Run from the project root: .\local\start-local.ps1
# Or from local\: .\start-local.ps1

param(
    [switch]$SkipMySQL,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "Pockie Ninja - Starting..."

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LocalDir = Join-Path $ProjectRoot "local"
$GameDir = Join-Path $ProjectRoot "work" "Pockie"
$LogDir = Join-Path $LocalDir "logs"
$AppBin = Join-Path $GameDir "app" "bin"

# Java 6 portable
$JavaExe = Join-Path $LocalDir "jdk6" "bin" "java.exe"
if (-not (Test-Path $JavaExe)) {
    $JavaExe = "java"  # fallback to system Java
}

# Python
$PythonExe = "python"

# MySQL
$MySQLDir = ""  # set if MySQL needs to be started manually

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Status($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] OK: $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] ERROR: $msg" -ForegroundColor Red
}

function Test-Port($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

function Wait-Port($port, $name, $timeoutSec = 30) {
    Write-Status "Waiting for $name on port $port..."
    $end = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $end) {
        if (Test-Port $port) {
            Write-Ok "$name is listening on port $port"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Err "$name did not start on port $port within ${timeoutSec}s"
    return $false
}

# ---------------------------------------------------------------------------
# Create log directory
# ---------------------------------------------------------------------------
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Pockie Ninja Offline Server - Starting    " -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Check MySQL
# ---------------------------------------------------------------------------
if (-not $SkipMySQL) {
    if (Test-Port 3306) {
        Write-Ok "MySQL already running on port 3306"
    } else {
        Write-Status "MySQL not detected on port 3306. Please start MySQL manually."
        Write-Host "  If using XAMPP: Start MySQL from XAMPP Control Panel" -ForegroundColor Gray
        Write-Host "  If using standalone: net start mysql" -ForegroundColor Gray
        Write-Host ""
        Read-Host "Press Enter after MySQL is running, or Ctrl+C to abort"
        if (-not (Test-Port 3306)) {
            Write-Err "MySQL still not available on port 3306. Aborting."
            exit 1
        }
    }
}

# ---------------------------------------------------------------------------
# 2. Flash policy server (port 843)
# ---------------------------------------------------------------------------
if (Test-Port 843) {
    Write-Ok "Flash policy server already running on port 843"
} else {
    Write-Status "Starting Flash policy server on port 843..."
    $policyScript = Join-Path $LocalDir "flash_policy.py"
    $policyLog = Join-Path $LogDir "flash_policy.log"
    $policyErr = Join-Path $LogDir "flash_policy.err.log"

    Start-Process -FilePath $PythonExe `
        -ArgumentList "`"$policyScript`" --port 843" `
        -WindowStyle Minimized `
        -RedirectStandardOutput $policyLog `
        -RedirectStandardError $policyErr

    Start-Sleep -Seconds 1
    if (Test-Port 843) {
        Write-Ok "Flash policy server started on port 843"
    } else {
        Write-Err "Flash policy server failed to start (port 843 may require admin)"
        Write-Host "  Try: Run PowerShell as Administrator" -ForegroundColor Gray
        Write-Host "  Or:  The proxy on 7001 also handles policy requests" -ForegroundColor Gray
    }
}

# ---------------------------------------------------------------------------
# 3. Web server (port 8080)
# ---------------------------------------------------------------------------
if (Test-Port 8080) {
    Write-Ok "Web server already running on port 8080"
} else {
    Write-Status "Starting web server on port 8080..."
    $webScript = Join-Path $LocalDir "local_web.py"
    $webLog = Join-Path $LogDir "web.log"
    $webErr = Join-Path $LogDir "web.err.log"

    Start-Process -FilePath $PythonExe `
        -ArgumentList "`"$webScript`" --port 8080 --game-root `"$GameDir`" --logfile `"$webLog`"" `
        -WindowStyle Minimized `
        -RedirectStandardError $webErr

    Wait-Port 8080 "Web server" 10
}

# ---------------------------------------------------------------------------
# 4. Game server - game01 (port 8001)
# ---------------------------------------------------------------------------
if (Test-Port 8001) {
    Write-Ok "Game01 already running on port 8001"
} else {
    Write-Status "Starting game01 on port 8001..."

    # Find the game server start script or jar
    $gameStartScript = $null
    $candidates = @(
        (Join-Path $AppBin "start_game01.bat"),
        (Join-Path $AppBin "game01.bat"),
        (Join-Path $AppBin "start.bat")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $gameStartScript = $c; break }
    }

    # Try to find the Java command from existing scripts
    $gameJar = $null
    $jarCandidates = Get-ChildItem -Path $AppBin -Filter "*.jar" -ErrorAction SilentlyContinue
    if ($jarCandidates) {
        $gameJar = $jarCandidates[0].FullName
    }

    $gameLog = Join-Path $LogDir "game01.log"
    $gameErr = Join-Path $LogDir "game01.err.log"

    if ($gameStartScript) {
        Write-Status "Using start script: $gameStartScript"
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c `"$gameStartScript`"" `
            -WorkingDirectory $AppBin `
            -WindowStyle Minimized
    } elseif ($gameJar) {
        Write-Status "Starting Java game server: $gameJar"
        # Use portable Java 6 if available
        $javaCmd = $JavaExe
        Start-Process -FilePath $javaCmd `
            -ArgumentList "-jar `"$gameJar`"" `
            -WorkingDirectory $AppBin `
            -WindowStyle Minimized `
            -RedirectStandardOutput $gameLog `
            -RedirectStandardError $gameErr
    } else {
        # Look for existing Java process commands in bat files
        $batFiles = Get-ChildItem -Path $AppBin -Filter "*.bat" -ErrorAction SilentlyContinue
        if ($batFiles) {
            Write-Status "Found batch files in app\bin:"
            $batFiles | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            Write-Status "Trying first batch file..."
            Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c `"$($batFiles[0].FullName)`"" `
                -WorkingDirectory $AppBin `
                -WindowStyle Minimized
        } else {
            Write-Err "No game server start script or jar found in $AppBin"
            Write-Host "  Please start game01 manually and ensure port 8001 is listening" -ForegroundColor Gray
        }
    }

    Wait-Port 8001 "Game01" 30
}

# ---------------------------------------------------------------------------
# 5. DmEnter gateway (port 7101)
# ---------------------------------------------------------------------------
if (Test-Port 7101) {
    Write-Ok "DmEnter already running on port 7101"
} else {
    Write-Status "Starting DmEnter on port 7101..."

    $dmenterExe = Join-Path $AppBin "DmEnter.exe"
    $dmenterIni = Join-Path $AppBin "DmEnter01.ini"
    $dmenterErr = Join-Path $LogDir "dmenter01.err.log"

    if (-not (Test-Path $dmenterExe)) {
        Write-Err "DmEnter.exe not found at $dmenterExe"
    } else {
        # Verify ini has correct ports
        if (Test-Path $dmenterIni) {
            $iniContent = Get-Content $dmenterIni -Raw
            Write-Status "DmEnter01.ini content:"
            Write-Host $iniContent -ForegroundColor Gray
        }

        Start-Process -FilePath $dmenterExe `
            -ArgumentList "`"$dmenterIni`"" `
            -WorkingDirectory $AppBin `
            -WindowStyle Minimized `
            -RedirectStandardError $dmenterErr

        Wait-Port 7101 "DmEnter" 15
    }
}

# ---------------------------------------------------------------------------
# 6. Socket proxy (port 7001)
# ---------------------------------------------------------------------------
if (Test-Port 7001) {
    Write-Ok "Socket proxy already running on port 7001"
} else {
    Write-Status "Starting socket proxy on port 7001 -> 7101..."
    $proxyScript = Join-Path $LocalDir "socket_proxy.py"
    $proxyLog = Join-Path $LogDir "socket_proxy.log"
    $proxyErr = Join-Path $LogDir "socket_proxy.err.log"

    Start-Process -FilePath $PythonExe `
        -ArgumentList "`"$proxyScript`" --proxy-port 7001 --dmenter-port 7101 --logfile `"$proxyLog`"" `
        -WindowStyle Minimized `
        -RedirectStandardError $proxyErr

    Wait-Port 7001 "Socket proxy" 10
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Port Status Summary                       " -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow

$ports = @(
    @{ Port = 3306; Name = "MySQL" },
    @{ Port = 843;  Name = "Flash Policy" },
    @{ Port = 8080; Name = "Web Server" },
    @{ Port = 8001; Name = "Game01 (Java)" },
    @{ Port = 7101; Name = "DmEnter" },
    @{ Port = 7001; Name = "Socket Proxy" }
)

$allOk = $true
foreach ($p in $ports) {
    $ok = Test-Port $p.Port
    if ($ok) {
        Write-Host ("  {0,-20} :{1,-6} OK" -f $p.Name, $p.Port) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-20} :{1,-6} DOWN" -f $p.Name, $p.Port) -ForegroundColor Red
        $allOk = $false
    }
}

Write-Host ""
if ($allOk) {
    Write-Host "  All services running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Game:  http://127.0.0.1:8080/littleninjasclient.html?nocache=$(Get-Random)" -ForegroundColor White
    Write-Host "  Admin: http://127.0.0.1:8080/admin.html" -ForegroundColor White
    Write-Host ""
    Write-Host "  IMPORTANT: Use Flash Browser (not Chrome/Edge)" -ForegroundColor Yellow
    Write-Host "  IMPORTANT: Close Flash Browser completely before restarting" -ForegroundColor Yellow
} else {
    Write-Host "  Some services are not running. Check the errors above." -ForegroundColor Red
    Write-Host "  Logs are in: $LogDir" -ForegroundColor Gray
}

Write-Host ""
$Host.UI.RawUI.WindowTitle = "Pockie Ninja - Server Running"
