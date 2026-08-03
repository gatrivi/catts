# Fish Speech + ZLUDA on RX 6600 (CATTS v0.7.3)

**Verdict:** use `patientx/fish-speech-zluda` (Fish Speech 1.5). Author clocks `--half` ~3× on an RX 6600. Better quality/speed than Pocket/Kokoro-on-CPU for clone work. Weights are **CC-BY-NC-SA-4.0** (non-commercial).

CATTS talks to its HTTP API (`POST /v1/tts`). Engine id: `fish`.

---

## Why not the others

| Engine | Issue on this rig |
|--------|-------------------|
| Pocket / Kokoro (CPU) | Too slow for the quality you want |
| XTTS | Coqui CPML gate + CPU/AMD pain |
| Chatterbox | No solid AMD GPU path |
| Cloud neural TTS | Out of scope |

---

## Steps (do in order)

### 0 — already done in repo
CATTS client + health wiring + scripts (`setup_fish_zluda.ps1`, `start_fish_api.ps1`).

### 1 — HIP / ZLUDA host prep (you, on Windows)
0. **Disk:** keep ~**15 GB free** on the drive that holds `fish-speech-zluda` (torch CUDA wheel ~2.7 GB + `fish-speech-1.5` weights + venv/ZLUDA; peak during install can be higher).
1. Install **Python 3.10.11 or 3.11** from python.org (not Store). Add to PATH.
2. Install [VC++ redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
3. Install **HIP SDK 5.7.1** (Windows).
4. System env:
   - `HIP_PATH` = `C:\Program Files\AMD\ROCm\5.7\`
   - add `C:\Program Files\AMD\ROCm\5.7\bin` to `Path`
5. **RX 6600 (gfx1032):** replace rocBLAS library files from [Brknsoul/ROCmLibs](https://github.com/brknsoul/ROCmLibs) into  
   `C:\Program Files\AMD\ROCm\5.7\bin\rocblas\library` (backup first).
6. Latest AMD driver. Remove leftover NVIDIA drivers if any.
7. Reboot. If you have an AMD iGPU too, set `HIP_VISIBLE_DEVICES=1` so the dGPU is used.

### 2 — install Fish Speech ZLUDA
From CATTS repo (cmd or PowerShell):

```powershell
.\scripts\setup_fish_zluda.ps1
```

Or manually:

```bat
git clone https://github.com/patientx/fish-speech-zluda.git
cd fish-speech-zluda
install-amd.bat
```

### 3 — point CATTS at it
`.env`:

```txt
CATTS_TTS_ENGINE=fish
CATTS_FISH_URL=http://127.0.0.1:8080
CATTS_FISH_ROOT=E:\path\to\fish-speech-zluda
CATTS_TTS_SPEED=0.9
```

`CATTS_TTS_SPEED=0.9` ≈ 10% slower (ffmpeg `atempo` after Fish synth; Kokoro uses native `speed`).

### 4 — start API (not just WebUI)
```powershell
.\scripts\start_fish_api.ps1
```

Uses `zluda.exe -- python tools\api_server.py --half --listen 127.0.0.1:8080`.  
First generation: “Compiling…” / looks idle once — normal ZLUDA cache.

### 5 — verify
```powershell
curl http://127.0.0.1:8080/v1/health
# {"status":"ok"}

# restart CATTS, then:
curl http://127.0.0.1:59200/health
# tts_engine=fish, tts_ready=true
```

Save a voice sample (10–30s), then Live TTS / audiobook.

---

## Sources

- https://github.com/patientx/fish-speech-zluda
- https://github.com/brknsoul/ROCmLibs
- Fish API: `POST /v1/tts`, health `GET /v1/health`
