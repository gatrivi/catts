@echo off
rem CATTS local: un solo terminal para modelos y apps (no abre ventanas nuevas).
rem Uso: CATTS.cmd            menu    CATTS.cmd status    CATTS.cmd check
rem      CATTS.cmd start bonsai2 --preset low   CATTS.cmd switch qwen35
rem      CATTS.cmd stop all   CATTS.cmd chat mini   CATTS.cmd list
title CATTS local - modelos y apps
"E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe" "%~dp0scripts\hub.py" %*
if errorlevel 1 pause