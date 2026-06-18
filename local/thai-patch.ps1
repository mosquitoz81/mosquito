# thai-patch.ps1 - Thai/English translation patch wrapper
# Usage:
#   .\local\thai-patch.ps1 scan     # preview changes
#   .\local\thai-patch.ps1 apply    # apply translation patch
#   .\local\thai-patch.ps1 revert   # revert to original Indonesian

param(
    [Parameter(Position=0)]
    [ValidateSet("scan", "apply", "revert")]
    [string]$Mode = "scan",

    [switch]$Verbose
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$GameRoot = Join-Path $ProjectRoot "work" "Pockie"
$PatchScript = Join-Path $ScriptDir "thai_patch.py"

if (-not (Test-Path $GameRoot)) {
    Write-Host "ERROR: Game root not found: $GameRoot" -ForegroundColor Red
    exit 1
}

$args_ = @("$PatchScript", "--game-root", "$GameRoot", "--mode", $Mode)
if ($Verbose) { $args_ += "--verbose" }

Write-Host "Running thai_patch.py in '$Mode' mode..." -ForegroundColor Cyan
Write-Host ""

python @args_

Write-Host ""
if ($Mode -eq "scan") {
    Write-Host "To apply: .\local\thai-patch.ps1 apply" -ForegroundColor Yellow
} elseif ($Mode -eq "apply") {
    Write-Host "To revert: .\local\thai-patch.ps1 revert" -ForegroundColor Yellow
}
