@echo off
rem Spark-X2.5-4B Q8 self-try (first local run 2026-09-18). Keep window open; Ctrl+C stops.
rem REQUIRES llama-vulkan-b10964 (older llama-vulkan dir rejects arch 'spark2_5').
rem Measured: 16.5 tok/s decode, native tool calls PASS. 1M ctx claimed - untested above 16K.
rem Port 9105. Zed provider "spark" points here.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'Z:\Models\runtime\llama-vulkan-b10964\llama-server.exe' -m 'Z:\catts\local-coding\data\models\spark25\Spark-X2.5-4B-Q8_0.gguf' --host 127.0.0.1 --port 9105 --alias spark25 -ngl 99 -c 16384 -np 1 -fa on --no-warmup --jinja"
if errorlevel 1 pause
