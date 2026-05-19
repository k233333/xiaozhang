@echo off
:: 移除小张开机自启动
set TASK_NAME=XiaoZhang_VoiceAssistant
schtasks /delete /tn "%TASK_NAME%" /f
if %errorlevel% equ 0 (
    echo [OK] 已移除开机自启动: %TASK_NAME%
) else (
    echo [INFO] 任务不存在或已移除
)
pause
