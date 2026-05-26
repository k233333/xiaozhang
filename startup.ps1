# ============================================================
# XiaoZhang Auto-Start Script (v4.1 - CC Brain)
# Triggered by Windows Task Scheduler, 2 min delay after logon
# ============================================================

$ErrorActionPreference = "Continue"

$XZ_DIR    = "D:\11111begin\xiaozhang"
$XZ_PYTHON = "$XZ_DIR\.venv\Scripts\python.exe"
$XZ_MAIN   = "$XZ_DIR\main.py"

$LOG_DIR = "$XZ_DIR\logs"
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$LOG_FILE  = "$LOG_DIR\startup_$timestamp.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LOG_FILE -Value $line
}

Log "=== XiaoZhang startup begin (v4.1) ==="

# --- Step 1: Preload models to GPU ---
Log "Step 1: Preload local models to GPU..."
try {
    $result = & $XZ_PYTHON -u "$XZ_DIR\scripts\preload_models.py" 2>&1
    $result | ForEach-Object { Log "  $_" }
} catch {
    Log "  Model preload failed: $_"
}

# --- Step 2: Open log monitor terminal ---
Log "Step 2: Open log monitor terminal..."
$logScript = @"
`$host.UI.RawUI.WindowTitle = 'XiaoZhang Log'
`$logFile = '$($LOG_DIR -replace "'","''")\xiaozhang.log'
Write-Host '=== XiaoZhang Live Log ===' -ForegroundColor Cyan
Write-Host "Log: `$logFile" -ForegroundColor DarkGray
Write-Host ''
if (Test-Path `$logFile) {
    Get-Content `$logFile -Tail 20
}
Get-Content `$logFile -Wait -Tail 0
"@
$logScriptPath = "$XZ_DIR\scripts\_log_monitor.ps1"
$logScript | Out-File -FilePath $logScriptPath -Encoding UTF8 -Force

Start-Process -FilePath "C:\Users\k9211\scoop\apps\pwsh\current\pwsh.exe" `
    -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $logScriptPath `
    -WindowStyle Normal

# --- Step 3: Start XiaoZhang daemon with auto-restart watchdog ---
Log "Step 3: Start XiaoZhang daemon (with auto-restart)..."

# 守护进程崩溃后自动重启的 watchdog 脚本
$watchdogScript = @"
`$XZ_PYTHON = '$XZ_PYTHON'
`$XZ_MAIN   = '$XZ_MAIN'
`$XZ_DIR    = '$XZ_DIR'
`$restartCount = 0
while (`$true) {
    Write-Host "[`$(Get-Date -Format 'HH:mm:ss')] Starting XiaoZhang (restart #`$restartCount)..." -ForegroundColor Green
    `$proc = Start-Process -FilePath `$XZ_PYTHON -ArgumentList `$XZ_MAIN, 'start' ``
        -WorkingDirectory `$XZ_DIR -WindowStyle Hidden -PassThru -Wait
    `$exitCode = `$proc.ExitCode
    Write-Host "[`$(Get-Date -Format 'HH:mm:ss')] XiaoZhang exited (code=`$exitCode), restarting in 5s..." -ForegroundColor Yellow
    `$restartCount++
    Start-Sleep -Seconds 5
}
"@
$watchdogPath = "$XZ_DIR\scripts\_watchdog.ps1"
$watchdogScript | Out-File -FilePath $watchdogPath -Encoding UTF8 -Force

$wdProc = Start-Process -FilePath "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File", $watchdogPath `
    -WorkingDirectory $XZ_DIR -WindowStyle Hidden -PassThru
Log "  Watchdog PID: $($wdProc.Id)"

# --- Step 4: Show ready notification ---
Log "Step 4: Show ready toast..."
Start-Sleep -Seconds 3
try {
    & $XZ_PYTHON -c "from src.ui.toast import show_reply; show_reply('小张已启动', 4.0)" `
        2>&1 | Out-Null
} catch {
    Log "  Toast failed (non-critical)"
}

Log "=== XiaoZhang startup complete ==="
