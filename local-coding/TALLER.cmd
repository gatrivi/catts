@echo off
title Taller local - sin suscripcion
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\taller.ps1" %*
