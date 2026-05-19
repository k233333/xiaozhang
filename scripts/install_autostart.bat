@echo off
:: 注册小张为 Windows 开机自启动（通过计划任务）
:: 用法：右键"以管理员身份运行"本脚本

set TASK_NAME=XiaoZhang_VoiceAssistant
set PROJECT_DIR=%~dp0..
set UV_PATH=%USERPROFILE%\scoop\shims\uv.exe

echo ============================================
echo  小张 — 注册开机自启动
echo ============================================
echo.
echo  项目目录: %PROJECT_DIR%
echo  uv 路径:  %UV_PATH%
echo  任务名:   %TASK_NAME%
echo.

:: 删除旧任务（如果存在）
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 创建计划任务：用户登录时启动，延迟 30 秒（等系统稳定）
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%UV_PATH%\" run --directory \"%PROJECT_DIR%\" python main.py start" ^
  /sc onlogon ^
  /delay 0000:30 ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] 已注册开机自启动任务: %TASK_NAME%
    echo     登录后延迟 30 秒启动小张守护进程
    echo.
    echo 管理方式:
    echo   查看: schtasks /query /tn "%TASK_NAME%"
    echo   删除: schtasks /delete /tn "%TASK_NAME%" /f
    echo   手动触发: schtasks /run /tn "%TASK_NAME%"
) else (
    echo.
    echo [FAIL] 注册失败，请确认以管理员身份运行
)

pause
