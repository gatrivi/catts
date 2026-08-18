# CATTS (v0.7.2)

Local **audiobook + voice** tool for CPU/AMD (no NVIDIA required).

## QuÃ© hace (flujos)

### 1) Audiobook
1. SubÃ­s un libro: `PDF / EPUB / DOCX / TXT`
2. Se procesa en background: limpieza de texto + particiÃ³n en capÃ­tulos
3. Se genera audio con TTS y se reproduce desde la â€œLibraryâ€

### 2) Tu voz (EN / ES)
1. GuardÃ¡s una muestra leyendo el script
2. STT calcula **script match** y muestra el resultado en la card de voz
3. Esa voz se usa para **Live interpreting**

### 3) Live interpreting (clon de voz)
`POST /tts/live` genera audio en tu voz clon (XTTS) para frases cortas.

### 4) Tools (STT + Translate)
- `POST /stt/transcribe` (Whisper local)
- `POST /stt/translate` (Argos offline ENâ†”ES; opcional Madlad400 para mejor calidad)

## AutenticaciÃ³n (API key)

Los endpoints requieren header `X-API-Key` **solo si** `CATTS_API_KEY` estÃ¡ seteada (si estÃ¡ vacÃ­a, la API queda abierta).
La UI lee/escribe `localStorage` con la key `catts_api_key` y la envÃ­a como `X-API-Key`.

`.env.example`:
```txt
CATTS_API_KEY=
CATTS_API_PORT=59200
CATTS_WORKER_URL=
CATTS_OCR_ENGINE=none
CATTS_OCR_FAST=tesseract
CATTS_OCR_BATCH=omniroute
CATTS_OMNIROUTE_URL=http://127.0.0.1:20128/v1
CATTS_TTS_ENGINE=xtts
CATTS_KOKORO_URL=http://127.0.0.1:8880
CATTS_KOKORO_VOICE=af_bella
CATTS_DEFAULT_VOICE_ID=
CATTS_ACCEPT_COQUI_CPML=
```

XTTS v2 requiere aceptar explÃ­citamente los tÃ©rminos Coqui CPML/comerciales. Solo despuÃ©s de leerlos, seteÃ¡ `CATTS_ACCEPT_COQUI_CPML=1`.
Para probar TTS local sin clonaciÃ³n ni gate de XTTS, arrancÃ¡ Kokoro-FastAPI y seteÃ¡ `CATTS_TTS_ENGINE=kokoro`.

## Run (API + UI)

```powershell
cd e:\zengatrivi-drive-e\catts
npm start
# or: .\scripts\start_api.ps1
```

Health: `npm run health` â†’ `http://127.0.0.1:59200/health`

Equiv. manual:
```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

AbrÃ­:
- `http://127.0.0.1:59200/`

La UI es `static/index.html`.
ES HQ default: `.env` â†’ `CATTS_TTS_ENGINE=edge` (`es-AR-TomasNeural`).

## Endpoints (backend)

- `GET /health`
- `POST /jobs/audiobook` (upload libro â†’ job)
- `GET /jobs`
- `GET /jobs/{job_id}/files`
- `GET /jobs/{job_id}/chapters/{chapter_num}/audio`
- `GET /jobs/{job_id}/result`
- `POST /voices` (guardar sample)
- `GET /voices`
- `POST /voices/{id}/evaluate?wait=true` (script match)
- `GET /voices/{id}/sample` (reproducir sample)
- `POST /tts/live` (live interpreting)
- `POST /stt/transcribe`
- `POST /stt/translate`
- `POST /ocr/fast` (Tesseract â€” page now â†’ `data/ocr/*-fast.md`)
- `POST /ocr/batch` (PDF or N images + optional `titles`; quality path)
- `POST /ocr/image` / `POST /ocr/pdf` (legacy aliases â†’ batch / Unlimited worker)

## Motores (quÃ© usa)

Resumen (segÃºn `services/*`):
- **TTS rÃ¡pido local**: Kokoro-FastAPI (`CATTS_TTS_ENGINE=kokoro`, sin clonaciÃ³n)
- **Voice clone TTS**: XTTS v2 (vÃ­a worker persistente, requiere aceptar tÃ©rminos Coqui)
- **STT + script match**: faster-whisper (`small` por defecto)
- **Translate ENâ†”ES**: Argos offline (default) o Madlad400 offline (mejor calidad)
  Para Madlad: descargalo una vez con `python scripts/setup_madlad_model.py` (se guarda en `data/madlad_runtime/model`) y dejÃ¡ `CATTS_TRANSLATE_ENGINE=auto` o `madlad`.
- **Lectura de libros**: extracciÃ³n + particiÃ³n en capÃ­tulos en CPU

OCR:
- **Fast:** `CATTS_OCR_FAST=tesseract` (binario Tesseract en PATH).
- **Batch:** `CATTS_OCR_BATCH=omniroute` (default) | `unlimited` | `tesseract`. Audiobook jobs OCR page 1 first, then buffer.
- Legacy: `CATTS_OCR_ENGINE=unlimited` + `CATTS_WORKER_URL` still works.
## LÃ­mites / â€œcÃ³mo se rompeâ€

- Live TTS requiere referencia de audio de la voz (por ejemplo `reference.wav` o `sample.wav` en `data/voices/<id>/`).
- Generar libros completos en CPU puede ser lento (esp. por el pipeline de TTS por capÃ­tulos).
- Si falta XTTS instalado o estÃ¡ â€œcoldâ€, el primer uso puede tardar mÃ¡s hasta que el worker quede â€œhotâ€.

## VerificaciÃ³n rÃ¡pida (UI / terminal)

En la UI hay un panel `Diagnostics` con un â€œsmoke checkâ€ que te muestra exactamente en quÃ© step fallÃ³.

Desde terminal, para detectar en quÃ© paso se rompe el stack (API + STT + Translate + Live TTS + audio decode), corrÃ©:

```powershell
.\.venv\Scripts\python.exe scripts\_smoke_test.py
```

Para chequear el entorno local antes de arrancar:

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

La UI y el smoke usan el header `X-API-Key` si `CATTS_API_KEY` estÃ¡ seteada.

## Docs

- Contexto/MVP: `docs/CONTEXT.md`
- Kokoro Plus API (localhost): `docs/KOKORO_PLUS_API_READY.md`
- Estado nocturno (honesto): `docs/NIGHT_REPORT.md`
- AuditorÃ­a actual / setup roto: `docs/PROJECT_AUDIT.md`
- VerificaciÃ³n MVP: `docs/MVP_VERIFICATION.md`
- Handoff: LiteUI integration: `docs/HANDOFF_LiteUI_Integration.md`
- Handoff: Pocket-TTS engine: `docs/HANDOFF_PocketTTS_Engine.md`
- Cambios: `CHANGELOG.md`


## OpenCode + FreeLLMAPI

FreeLLMAPI corre en Windows sin Docker/WSL. La versiÃ³n desktop instalada usa `http://127.0.0.1:31415/v1` (la documentaciÃ³n upstream todavÃ­a menciona `:3001`).

Primer arranque:

```powershell
cd E:\zengatrivi-drive-e\catts
.\scripts\start_freellmapi.ps1
$env:FREELLMAPI_API_KEY = (& sqlite3.exe "$env:APPDATA\FreeLLMAPI\freeapi.db" "select value from settings where key='unified_api_key';").Trim()
opencode run "respond exactly OK" --model freellmapi/kilo-auto
```

VerificaciÃ³n directa:

```powershell
.\scripts\verify_freellmapi.ps1
```

El piloto usa Kilo y AI Horde como proveedores `keyless`; Kilo es el Ãºnico que publica un modelo servible en el catÃ¡logo actual. No se crean cuentas duplicadas ni se configura Cursor. El failover entre dos proveedores todavÃ­a no se declara validado hasta que el segundo publique un modelo y una llamada real muestre el cambio de `X-Routed-Via`.

Plan B si FreeLLMAPI falla:

```powershell
npm.cmd install -g omniroute
omniroute
```

Luego usar `http://127.0.0.1:20128/v1` y la clave del dashboard de OmniRoute.


## Comandos simples de CATTS

```powershell
npm run catts              # reinicia API y muestra estado
npm run queue:status       # estado de API, Fish y cola
npm run queue:folder       # agrega libros nuevos desde data/books/inbox
```

Para un libro: crear `data/books/inbox/Nombre/chapters/` y poner allí un `.txt` por capítulo. Luego `npm run queue:folder` y arrancar la cola con `\.\.venv\Scripts\python.exe scripts\workqueue_runner.py`. La cola guarda estado en `data/workqueue/state.json`; `RUNNING`, `STALE/STOPPED`, `FAILED` e `IDLE` son estados explícitos.
