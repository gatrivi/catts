@echo off
rem MiniCPM5-2B Q8 @ 131K coding server, hand use. Keep this window open; Ctrl+C stops.
rem Close other model servers first (needs most of the 8 GB VRAM at 131K ctx).
rem Chat UI / API: http://127.0.0.1:9104  (OpenAI-compatible /v1)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_minicpm5_coding.ps1"
if errorlevel 1 pause
