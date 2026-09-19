@echo off
title Smol local
"E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe" "%~dp0scripts\smol.py" %*
if errorlevel 1 pause
