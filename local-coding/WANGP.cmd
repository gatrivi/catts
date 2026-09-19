@echo off
title Wan2GP local (imagen/video)
"E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe" "%~dp0scripts\wangp_local.py" %*
if errorlevel 1 pause
