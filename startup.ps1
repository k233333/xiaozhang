# coding: utf-8
# ============================================================
# 小张 + Hermes 开机自启动脚本
# 由 Windows 计划任务触发，开机后延迟 120 秒执行
# ============================================================

$ErrorActionPreference = "Continue"

# --- 路径配置 ---
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

# --- Step 1: 预加载模型到 GPU（验证 DirectML 可用） ---
# 模型清单：wake_word(26KB) + silero_vad(2.2MB) + sensevoice(894MB)
# OmniParser 暂未转 ONNX，跳过（D8-9 阶段补）
# 游戏模式下 watchdog 会自动 unload sensevoice 释放显存
Log "Step 1: 预加载本地模型到 GPU..."
& $XZ_PYTHON -u -c @"
import onnxruntime as ort, time, sys, os
models = [
    ('wake_word', r'$XZ_DIR\models\wake_word\xiaozhang_wakeword.onnx'),
    ('silero_vad', r'$XZ_DIR\models\silero_vad.onnx'),
    ('sensevoice', r'$XZ_DIR\models\sensevoice_small.onnx'),
]
all_gpu = True
for name, path in models:
    if not os.path.isfile(path):
        print(f'  {name}: SKIP (file missing)', flush=True)
        continue
    t0 = time.time()
    sess = ort.InferenceSession(path, providers=['DmlExecutionProvider','CPUExecutionProvider'])
    gpu = 'DmlExecutionProvider' in sess.get_providers()
    tag = 'GPU' if gpu else 'CPU'
    print(f'  {name}: {tag} ({time.time()-t0:.1f}s)', flush=True)
    if not gpu:
        all_gpu = False
        print(f'  WARNING: {name} fell back to CPU', file=sys.stderr)
if all_gpu:
    print('All models on GPU.', flush=True)
else:
    print('WARNING: some models on CPU.', flush=True)
"@ 2>&1 | ForEach-Object { Log $_ }

# --- Step 2: 启动 Hermes gateway（后台服务，供语音唤醒调用） ---
Log "Step 2: 启动 Hermes gateway..."
$hermesProc = Start-Process -FilePath $HERMES_EXE -ArgumentList "gateway", "start" `
    -WorkingDirectory $HERMES_DIR -WindowStyle Hidden -PassThru
Log "  Hermes gateway PID: $($hermesProc.Id)"

# --- Step 3: 启动小张守护进程（唤醒词监听 + 语音识别 + 技能执行） ---
Log "Step 3: 启动小张守护进程..."
$xzProc = Start-Process -FilePath $XZ_PYTHON -ArgumentList $XZ_MAIN, "daemon" `
    -WorkingDirectory $XZ_DIR -WindowStyle Hidden -PassThru
Log "  小张 daemon PID: $($xzProc.Id)"

# --- Step 4: 弹出就绪通知 ---
Log "Step 4: 弹出就绪气泡..."
& $XZ_PYTHON -c "from src.ui.toast import show_reply; show_reply('小张已就绪，随时听候吩咐', 4.0)"

Log "=== 启动完成 ==="
