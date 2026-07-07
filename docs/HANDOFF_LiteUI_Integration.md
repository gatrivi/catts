# CATTS ↔ LiteUI Studio Handoff (ready for next person)

**CATTS version:** `v0.7.2`  
**What this integration does:** clones LiteUI-Studio into this repo and adds CATTS API + UI controls to start it and open its Gradio page.

---

## 1) Repo layout (what’s been added)

- LiteUI repo clone:
  - `external/LiteUI-Studio/`
- CATTS backend routes:
  - `api/routes/liteui.py`
- CATTS UI changes:
  - `static/index.html` adds a **LiteUI Studio** panel

---

## 2) CATTS API: LiteUI controls

All `/liteui/*` endpoints require the CATTS API key logic already used by the rest of the UI (`X-API-Key`, via `CATTS_API_KEY` in `.env`).

### 2.1 `GET /liteui/status`
Returns:
- whether LiteUI Gradio UI port is open (`7860`)
- whether LiteUI backend/engine port is open (`8188`)
- whether `external/LiteUI-Studio/start_en.py` exists
- whether the embedded interpreter exists at:
  - `external/LiteUI-Studio/python/python.exe`

### 2.2 `POST /liteui/start`
Spawns LiteUI by running:
- `external/LiteUI-Studio/start_en.py` (from within `external/LiteUI-Studio/`)

That script will then spawn:
- the embedded ComfyUI backend on `127.0.0.1:8188`
- the Gradio UI on `127.0.0.1:7860`

---

## 3) CATTS UI: “LiteUI Studio” panel

In `static/index.html` there is a new collapsible panel:
- **LiteUI Studio — image/video workstation**

Buttons:
- `Start`: calls `POST /liteui/start`
- `Open UI`: opens the Gradio UI URL from `/liteui/status`:
  - `http://127.0.0.1:7860/`

Notes:
- This integration does **not** embed the LiteUI UI inside CATTS (no iframe); it opens a new tab.

---

## 4) What you must install/unpack for LiteUI to actually run

Cloning LiteUI does not include the heavyweight model runtime assets.

LiteUI’s `start_en.py` explicitly expects:
1. **Embedded python**:
   - `external/LiteUI-Studio/python/python.exe`
   - Usually comes from LiteUI’s “Core Edition” / provided `python.zip`.
2. **LiteUI Core files** (models + backend_comfyui folder + ffmpeg), per LiteUI’s README.

### Minimum checklist (for the `Start` button to succeed)
1. Unzip LiteUI-provided `python.zip` into `external/LiteUI-Studio/`
   - ensure `external/LiteUI-Studio/python/python.exe` exists
2. Ensure `external/LiteUI-Studio/start_en.py` exists (it does after clone)

If `python/python.exe` is missing, CATTS will show a clear error in the LiteUI panel and `POST /liteui/start` will fail.

### Full checklist (for LiteUI to generate working outputs)
- Follow LiteUI “Core Edition” setup steps:
  - unzip Core edition assets
  - place ffmpeg binaries where LiteUI expects them
  - install/prepare `backend_comfyui/` and required models under its expected directories

---

## 5) Ports and runtime expectations

- LiteUI Gradio UI: `127.0.0.1:7860`
- LiteUI backend (ComfyUI): `127.0.0.1:8188`

If another service already uses those ports, the “status” endpoint will show ports as not open and `Start` may fail.

---

## 6) Current limitations / follow-ups

1. **No iframe embedding** yet (open in new tab is used).
2. **No model download automation** inside CATTS.
3. Integration focuses on “start + open UI”; no request proxying from CATTS to LiteUI.

