@echo off
title Local models menu
:menu
cls
echo  ===============================
echo   LOCAL MODELS (one at a time)
echo  ===============================
echo.
echo  1  Bonsai-2 27B  (smartest, slow ~13 t/s, port 9103)
echo  2  NeoHorse 4B   (fast ~36 t/s, port 9107)
echo  3  Spark 4B      (fast ~16 t/s, port 9105)
echo  4  MiniCPM5 2B   (long docs 131K, port 9104)
echo  5  Show what is running
echo  6  Stop ALL model servers
echo  0  Exit
echo.
set /p c="Pick: "
if "%c%"=="1" call Z:\catts\local-coding\BONSAI2.cmd & goto menu
if "%c%"=="2" powershell -NoProfile -ExecutionPolicy Bypass -File Z:\catts\local-coding\scripts\start_neohorse.ps1 & goto menu
if "%c%"=="3" call Z:\catts\local-coding\SPARK.cmd & goto menu
if "%c%"=="4" call Z:\catts\local-coding\MINICPM5-CODING.cmd & goto menu
if "%c%"=="5" powershell -NoProfile -Command "Get-Process llama-server -ErrorAction SilentlyContinue | Select-Object Id; pause" & goto menu
if "%c%"=="6" powershell -NoProfile -Command "Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force; Write-Host 'stopped'; pause" & goto menu
exit
