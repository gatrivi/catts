# CATTS (v0.7.2)

Local **audiobook + voice** tool for CPU/AMD (no NVIDIA required).

## Qué hace (flujos)

### 1) Audiobook
1. Subís un libro: `PDF / EPUB / DOCX / TXT`
2. Se procesa en background: limpieza de texto + partición en capítulos
3. Se genera audio con TTS y se reproduce desde la “Library”

### 2) Tu voz (EN / ES)
1. Guardás una muestra leyendo el script
2. STT calcula **script match** y muestra el resultado en la card de voz
3. Esa voz se usa para **Live interpreting**

### 3) Live interpreting (clon de voz)
`POST /tts/live` genera audio en tu voz clon (XTTS) para frases cortas.

### 4) Tools (STT + Translate)
- `POST /stt/transcribe` (Whisper local)
- `POST /stt/translate` (Argos offline EN↔ES)

## Autenticación (API key)

Los endpoints requieren header `X-API-Key` **solo si** `CATTS_API_KEY` está seteada (si está vacía, la API queda abierta).
La UI lee/escribe `localStorage` con la key `catts_api_key` y la envía como `X-API-Key`.

`.env.example`:
```txt
CATTS_API_KEY=
CATTS_API_PORT=59200
CATTS_WORKER_URL=
CATTS_OCR_ENGINE=none
CATTS_TTS_ENGINE=xtts
CATTS_KOKORO_URL=http://127.0.0.1:8880
CATTS_KOKORO_VOICE=af_bella
CATTS_DEFAULT_VOICE_ID=
CATTS_ACCEPT_COQUI_CPML=
```

XTTS v2 requiere aceptar explícitamente los términos Coqui CPML/comerciales. Solo después de leerlos, seteá `CATTS_ACCEPT_COQUI_CPML=1`.
Para probar TTS local sin clonación ni gate de XTTS, arrancá Kokoro-FastAPI y seteá `CATTS_TTS_ENGINE=kokoro`.

## Run (API + UI)

```powershell
cd e:\zengatrivi-drive-e\catts
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

Abrí:
- `http://127.0.0.1:59200/`

La UI es `static/index.html`.

## Endpoints (backend)

- `GET /health`
- `POST /jobs/audiobook` (upload libro → job)
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
- `POST /ocr/image` (requiere `CATTS_WORKER_URL`)
- `POST /ocr/pdf` (requiere `CATTS_WORKER_URL`)

## Motores (qué usa)

Resumen (según `services/*`):
- **TTS rápido local**: Kokoro-FastAPI (`CATTS_TTS_ENGINE=kokoro`, sin clonación)
- **Voice clone TTS**: XTTS v2 (vía worker persistente, requiere aceptar términos Coqui)
- **STT + script match**: faster-whisper (`small` por defecto)
- **Translate EN↔ES**: Argos offline (subproceso en `.venv`)
- **Lectura de libros**: extracción + partición en capítulos en CPU

OCR (PDF escaneados):
- Si `CATTS_OCR_ENGINE=unlimited` y hay `CATTS_WORKER_URL`, se delega a `WORKER_URL/ocr/pdf`.
- Si el worker devuelve `404`, cae a un fallback local basado en `pymupdf` (si está disponible).

## Límites / “cómo se rompe”

- Live TTS requiere referencia de audio de la voz (por ejemplo `reference.wav` o `sample.wav` en `data/voices/<id>/`).
- Generar libros completos en CPU puede ser lento (esp. por el pipeline de TTS por capítulos).
- Si falta XTTS instalado o está “cold”, el primer uso puede tardar más hasta que el worker quede “hot”.

## Verificación rápida (UI / terminal)

En la UI hay un panel `Diagnostics` con un “smoke check” que te muestra exactamente en qué step falló.

Desde terminal, para detectar en qué paso se rompe el stack (API + STT + Translate + Live TTS + audio decode), corré:

```powershell
.\.venv\Scripts\python.exe scripts\_smoke_test.py
```

Para chequear el entorno local antes de arrancar:

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

La UI y el smoke usan el header `X-API-Key` si `CATTS_API_KEY` está seteada.

## Docs

- Contexto/MVP: `docs/CONTEXT.md`
- Kokoro Plus API (localhost): `docs/KOKORO_PLUS_API_READY.md`
- Estado nocturno (honesto): `docs/NIGHT_REPORT.md`
- Auditoría actual / setup roto: `docs/PROJECT_AUDIT.md`
- Verificación MVP: `docs/MVP_VERIFICATION.md`
- Handoff: LiteUI integration: `docs/HANDOFF_LiteUI_Integration.md`
- Handoff: Pocket-TTS engine: `docs/HANDOFF_PocketTTS_Engine.md`
- Cambios: `CHANGELOG.md`

