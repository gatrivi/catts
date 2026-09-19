@echo off
rem Bonsai-2 27B PTQ1_0 self-try: keep this window open; Ctrl+C stops the server.
rem First chat reply takes minutes (~3.3 tok/s decode). Chat or light tool use only.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_bonsai2.ps1"
if errorlevel 1 pause
