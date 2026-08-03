# TTS engine compare (v0.7.3)

## Runtime switch (no .env)
- `GET /tts/engines` — list + ready flags
- `PUT /tts/engine` `{"engine":"fish|kokoro|xtts|…"}` — session override
- `DELETE /tts/engine` — back to `.env` default
- UI: Live panel → **TTS engine** dropdown + Use engine

Default still from `CATTS_TTS_ENGINE`; override is in-process only (lost on restart).

## Matrix
| Engine | Status | Notes |
|---|---|---|
| Kokoro | tried | no clone |
| XTTS | discarded | CPML + quality |
| Fish/ZLUDA | in progress | HIP 5.7 OK; needs Brknsoul gfx1032 rocBLAS in HIP path |
| Chatterbox | not installed | MIT; UI-selectable when pip'd |
| GPT-SoVITS | not wired | needs worker URL |
| OmniVoice | missing | external |

## Fish blocker (RX 6600 XT)
`rocBLAS … TensileLibrary.dat … gfx1032` — stock HIP has gfx1030 only.
Libs downloaded: `external/rocm-libs-gfx1032/`
Shadow HIP (writable): `external/hip57-shadow` — set `HIP_PATH` there when starting Fish.
Or copy `extracted/library/*` into `C:\Program Files\AMD\ROCm\5.7\bin\rocblas\library` (admin).
