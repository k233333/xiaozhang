@echo off
:: 手动启动小张（前台模式，看日志）
cd /d "%~dp0.."
uv run python main.py start
