# ============================================================
# XiaoZhang + Hermes Auto-Start Script
# Triggered by Windows Task Scheduler, 2 min delay after logon
# ============================================================

$ErrorActionPreference = "Continue"

# --- Paths ---
$XZ_DIR    = "D:\11111begin\xiaozhang"
$XZ_PYTHON = "$XZ_DIR\.venv\Scripts\python.exe"
$XZ_MAIN   = "$XZ_DIR\main.py"

$HERMES_DIR = "D:\11111begin\hermes-agent"
$HERMES_EXE = "$HERMES_DIR\venv\Scripts\hermes.exe"

$LOG_DIR = "$XZ_DIR\logs"
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$LOG_FILE  = "$LOG_DIR\startup_$timestamp.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LOG_FILE -Value $line
}

Log "=== XiaoZhang startup begin ==="
Log "Python: $XZ_PYTHON"
Log "Hermes: $HERMES_EXE"

# --- Step 1: Preload models to GPU ---
Log "Step 1: Preload local models to GPU..."
try {
    $result = & $XZ_PYTHON -u "$XZ_DIR\scripts\preload_models.py" 2>&1
    $result | ForEach-Object { Log "  $_" }
} catch {
    Log "  Model preload failed: $_"
}

# --- Step 2: Start Hermes gateway ---
Log "Step 2: Start Hermes gateway..."
if (Test-Path $HERMES_EXE) {
    try {
        $hermesProc = Start-Process -FilePath $HERMES_EXE -ArgumentList "gateway", "start" `
            -WorkingDirectory $HERMES_DIR -WindowStyle Hidden -PassThru
        Log "  Hermes gateway PID: $($hermesProc.Id)"
    } catch {
        Log "  Hermes gateway start failed: $_"
    }
} else {
    Log "  Hermes not found, skip"
}

# --- Step 3: Start XiaoZhang daemon ---
Log "Step 3: Start XiaoZhang daemon..."
try {
    $xzProc = Start-Process -FilePath $XZ_PYTHON -ArgumentList $XZ_MAIN, "start" `
        -WorkingDirectory $XZ_DIR -WindowStyle Hidden -PassThru
    Log "  XiaoZhang daemon PID: $($xzProc.Id)"
} catch {
    Log "  XiaoZhang daemon start failed: $_"
}

# --- Step 4: Show ready notification ---
Log "Step 4: Show ready toast..."
try {
    & $XZ_PYTHON -c "from src.ui.toast import show_reply; show_reply('XiaoZhang ready', 4.0)" 2>&1 | Out-Null
} catch {
    Log "  Toast failed (non-critical)"
}

Log "=== XiaoZhang startup complete ==="
