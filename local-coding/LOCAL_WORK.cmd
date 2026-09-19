@echo off
if "%~1"=="" (
  echo Uso: LOCAL_WORK.cmd "C:\zengatrivi\REACTJS\rosario-cards-v1"
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-work.ps1" -Project "%~1"
