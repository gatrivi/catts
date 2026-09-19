@echo off
rem Bonsai-2 auto-context proxy: keep this window open; Ctrl+C stops the proxy.
rem Requires the Bonsai-2 server running (BONSAI2.cmd). Clients point at :9106.
"E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe" "%~dp0scripts\bonsai2_proxy.py"
if errorlevel 1 pause
