# Heavy processes (16 GB RAM hygiene)

## Problem
Agents/scripts can leave many Python workers alive (Fish API retries, STT, XTTS, Kokoro, hermes). On 16 GB that crowds out Cursor + real work.

## What is “heavy” (ON only when needed)
| Process | Port / how | When ON | When OFF |
|---|---|---|---|
| CATTS API (uvicorn) | `:59200` | Using UI/API | Stop when done |
| FastKokoro server | `:8880` (`fastkokoro.exe`) | Batch TTS / live EN+ES | Stop after batch |
| Piper server | `:8881` (`scripts/piper_server.py`) | Legacy comparisons only | Normally off |
| STT worker | spawned by API (`stt_worker.py`) | Transcribe / voice eval | Kill after batch |
| XTTS worker | spawned by API (`xtts_worker.py`) | Clone TTS batch | Kill after batch |
| Fish API | `:8080` (`tools/api_server.py`) | Only after HIP works | Kill leftovers always |
| Madlad translate worker | on first madlad translate | Quality translate | Kill after batch |
| MeloTTS worker | spawned by API (`melotts_worker.py`) | ES book/live TTS | Kill after batch |
| Abogen (PyQt / web) | `abogen` / `:8808` | Chapter ebook → Kokoro GUI | Kill after use (`docs/ABOGEN.md`) |

Batch jobs: leave workers **ON for the whole batch**. After batch: **OFF**.

**Cassian bake-off** (`data/abogen/_run_bakeoff.cmd`): starts Kokoro if needed. When `BAKEOFF_DONE` in log → `npm run stop:heavy` (or kill FastKokoro). Edge needs no local server. Pocket runs in-process (no separate daemon).

## Quick status
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Select-Object ProcessId, @{n='MB';e={[int]($_.WorkingSetSize/1MB)}}, CommandLine |
  Sort-Object MB -Descending
```

## Kill leftovers (safe-ish)
```powershell
# Fish zombies
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'fish-speech|api_server\.py|run_webui' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Kokoro
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'kokoro_server' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# CATTS model workers (STT/XTTS) — only if API not needed
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'stt_worker|xtts_worker|translate_madlad' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Stopping the CATTS API process usually drops its child workers; Fish/Kokoro started separately must be killed explicitly.

## Agent rule
Before starting Fish/XTTS/Kokoro/STT: check free RAM and existing python count. Prefer one server. After work: stop heavy procs. Document ON/OFF in replies when relevant.
