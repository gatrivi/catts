# AGENTE PERSONAL LOCAL — eval de capacidades y plan (2026-09-25)

> Objetivo: cuanto se puede acercar un asistente personal **local** (con las manos en el
> browser) usando solo lo que ya esta en la caja. Todo escrito sin correr un solo modelo: la GPU
> la tiene el track GPU / campana nocturna. Solo lectura de disco + web.
> Zona: `local-coding/docs/` (este archivo), `local-coding/data/models/qwen3vl-4b/`,
> `local-coding/tmp/vl_*`. `SESSION_CONTEXT.md` y `HANDOFF_2026-09-25.md` son del agente GPU:
> no se tocan (ya se habia escrito ahi y se revirtio).

## 1. Restricciones que mandan

| Regla | Fuente | Efecto en este eval |
|---|---|---|
| GPU exclusiva, un modelo a la vez | `local-coding/AGENTS.md`, `BRIEFS/03_...md` §4 | cero inferencia en este doc; todo queda como plan |
| Sin descargas sin pedido | `local-coding/AGENTS.md` | solo se documentan candidatos; no se bajan pesos |
| Envios por ZCode computer-use, nunca por API | `TASKLIST.md` linea 41 | corrige mi propuesta previa de IMAP/SMTP para correo: **no aplica** |
| Una zona sin claim no se escribe | `BRIEFS/03_...md` §2-3 | claim en `CLAIMS.md`; `SESSION_CONTEXT.md` revertido |
| Git: uno a la vez | `BRIEFS/03_...md` §4 | sin commits aca |

## 2. Inventario verificado (lo que YA existe)

Leyendo disco, no suponiendo. `p` = ruta/puerto real.

| Capa | Pieza | Evidencia | Estado |
|---|---|---|---|
| **Manos** | ZCode computer-use (browser/Brave) | `C:/Users/DevTrivi/.zcode/v2/setting.json` tiene `computerUse`, `BrowserViewportPreference`, `BrowserAllowInsecureCertificates`; regla en `TASKLIST.md` | vivo, pero el loop lo maneja el modelo de ZCode (nube) |
| **Puente a modelos locales** | MCP `local-agents` | `local-coding/mcp_local_agents/server.py` (stdlib, tools `local_ask`/`local_status`); registrado en `C:/Users/DevTrivi/.zcode/cli/config.json` | **ya plugged**: ZCode puede preguntar a los llama-servers |
| **Loop de agente** | omp (oh-my-pi) | `api/services/omp_client.py` lo spawnea: `omp -p --mode json --model ... --cwd ... [--auto-approve]`; roles en `~/.omp/agent/config.yml` (`default: neohorse/neohorse`, `tools.approvalMode: yolo`) | vivo; el loop mas capable local |
| **Cerebro (modelos)** | roster local | `docs/MODEL_ROSTER.md` + `MODELS_INVENTORY.md` (medido): NeoHorse 4B 36 t/s tools 3/3 · Qwen3.5-9B 30-33 t/s @32K tools ok · Spark 4B 16-21 t/s tools parciales · Bonsai-2 27B TQ2 13 t/s ctx 8K tools 2/2 · E4B 41-42 t/s 3/3 · MiniCPM5 2B 48-60 t/s (no codigo) · qwen27 7 t/s · Gemma-3 12B tools 0/3 | 1 solo a la vez; <=5.5 GB entra en VRAM |
| **Ojos** | Qwen3-VL-4B + mmproj | `data/models/qwen3vl-4b/` (2381.6 + 432.9 MiB, sha256 == upstream), `STANDALONE['qwen3vl']` en `scripts/local_models.py` (:9112, `--mmproj` soportado), test verde | **instalado, sin validar en GPU** (smoke test pendiente) |
| **Voz** | TTS local (kokoro/xtts/chatterbox), STT | `services/*_tts.py`; `docs/VOICE_GATEWAY_LOCAL.md`: STT = Deepgram nube hoy | TTS local, STT no |
| **Memoria** | Supermemory :6767 | `local-coding/AGENTS.md`: lectura = solo embeddings (funciona sin modelo); ingesta = 1 slot de modelo + ~1 min/doc; `scripts/memory_ctx.py --get/--add` | viva, sin interfaz de agente |
| **Cola / agenda** | orquestador idle-time | `job-runner/cat-orchestrator.ps1` + `queue.json` (un item por tick, gated por ocioso); `local-coding/scripts/night_jobs.ps1` | existe el esqueleto |
| **HTTP de cara al mundo** | CATTS API :59200 | `api/main.py` (FastAPI): `/agent/prompt(/stream)`, `/jobs`, `/voices`, `/stt`, `/ocr`, `/diagnostics`, `/liteui`, `/static` | viva |
| **Control de flota** | hub + guard | `scripts/hub.py` (exclusividad GPU, pisos RAM), `scripts/agent_guard.py` (`GUARD.cmd status/fix/up`) | vivo |
| **Segundo plano** | chores API :9111, watchdog de stalls, small worker, advisor | `docs/CHORES_API.md`, `scripts/stall_watchdog.py` (revisor cloud cuando el local se traba) | vivos |
| **Navegador local** | Playwright/Selenium/pyautogui | NO instalados en el venv de E: | falta (Node 22 y Chrome 154 si estan) |

## 3. Vision: lo instalado y lo que falta probar

- Elegido `Qwen/Qwen3-VL-4B-Instruct-GGUF` (Apache-2.0, ctx 262K): Q4_K_M 2381.6 MiB +
  `mmproj-Q8_0` 432.9 MiB, sha256 local identico al upstream, revision `1cd86afb...`.
  Manifiestos `.verified.json` escritos.
- Por que ese: los runtimes ya sabian vision. Strings de `mtmd.dll` en `llama-vulkan` y
  `llama-vulkan-b10964`: `qwen3vl`, `qwen2vl`, `internvl`, `minicpmv`, `gemma3n`. El fork
  **Prism NO** (mtmd viejo) -> el VLM jamas corre con `PRISM_RUNTIME`.
- Descarga (leccion dura): `hf_hub_download` con **hf_xet se colgo en 109.5 MiB (0 MiB/s)** y
  su reintento HTTP se reinicio; `curl` en background no escribia. Estable: `tmp/vl_fetch.py`
  (`requests` + `Range` resume, log cada 64 MiB, 3-28 MiB/s). Para HF en esta caja:
  `HF_HUB_DISABLE_XET=1`.
- Wiring: `standalone_args()` ahora honra `spec['mmproj']`; entrada en `STANDALONE` (menu 6,
  filas 1-5 intactas); test `tests/test_smol.py::test_qwen3vl_standalone_args_carry_the_mmproj`.
- **Sin validar**: que el encoder de vision vaya bien en Vulkan/RX 6600, tok/s, y si VRAM
  alcanza con la foto de pantalla. Ground truth listo: `tmp/vl_make_test_image.ps1` dibuja un
  browser falso; el boton verde "Search jobs" esta en (500,600)-(800,644), centro **650,622**.
  Correr `tmp/vl_smoke.ps1` cuando la GPU sea de alguien mas.
- Alternativas (no bajadas, con numeros): `Holo1.5-3B` (Qwen2.5-VL-3B, ScreenSpot-Pro **51.5**,
  el mejor grounding por GB; quants de terceros + mmproj de `ggml-org`; licencia research en 3B)
  ~2.9 GiB · `SmolVLM2-2.2B-Agentic-GUI` 1.85 GiB, 8K ctx, sin benchmarks · `MAI-UI-8B`
  (Qwen3-VL, GUI-agent) ~5.8 GiB con mmproj: no entra comodo en 8 GB.
- Y el punto del usuario: para **navegar, drag-select y copiar texto** no hace falta VLM.
  Camino sin modelo: DOM/CDP (Playwright), UI Automation para apps nativas, y OCR nativo de
  Windows con sus word-boxes. El VLM es para "donde clickear" y para imagenes/canvas/PDF.

## 4. Hallazgos duros (bloqueos verificados, con archivo y linea)

1. **El agente por HTTP no es local hoy.** `api/routes/agent.py:32` devuelve 503 si el backend
   es `omp` y falta el token de LM Studio, y `config.py:39` pone
   `OMP_MODEL = "lm-studio/ornith-1.0-9b"`. O sea: `/agent/prompt` no habla con `:9104/:9107`.
   Fix chico: gatear el token solo cuando el modelo empieza con `lm-studio/`, y
   `CATTS_OMP_MODEL=neohorse/neohorse`. Es el arreglo de mayor rendimiento de este doc.
2. **`--auto-approve` por defecto.** `services/omp_client.py:60,73` lo anade si no se dice lo
   contrario, y `~/.omp/agent/config.yml` tiene `tools.approvalMode: yolo`. Un agente asi, con
   bash/files, leyendo correo y web, es la peor combinacion posible (inyeccion de prompt).
3. **OCR no es local**: `api/routes/ocr.py` exige `CATTS_WORKER_URL` (worker remoto
   "Unlimited-OCR" en SGLang, `services/ocr_client.py`). Local: el VLM nuevo o el OCR nativo de
   Windows.
4. **STT no es local**: `docs/VOICE_GATEWAY_LOCAL.md` (Deepgram nube). El TTS si es local
   (`services/kokoro_tts.py`, `xtts_tts.py`, `chatterbox_tts.py`).
5. **No hay manos locales**: Playwright/Selenium/pyautogui no estan en el venv de E:. Node 22 y
   Chrome 154 si, pero Chrome 136+ bloquea CDP sobre el perfil default -> perfil dedicado
   (`--user-data-dir`), login a mano una vez.
6. **La cola idle-time apunta a un script inexistente**: `job-runner/queue.json` describe
   `scripts/job-mule.ps1` ("unattended apply pass") y ese archivo no esta en `Z:/catts/scripts`.
7. **Conflicto de horario**: `llama-server-evening` 23:30 (Qwen3.5-9B ~5.3 GB) hasta
   `morning-stop` 07:30, y la campana 02:30 exige 11 GB RAM libres (`BRIEFS/02_...` §4).
   `hub.py` se niega a arrancar dos modelos: un asistente 24/7 no puede convivir con eso.
8. **Memoria sin interfaz de agente**: supermemory lee sin modelo, pero la ingesta necesita un
   slot ocioso (~1 min/doc) -> no puede ir sincronica en un turno.
9. **Herramientas "magras" a medio camino**: `scripts/chores_api.py` ya expone `/agent/turn` con
   tools `read,grep,glob` (+`write,edit` solo con `--allow-writes`), sin bash, token bearer y
   journals en `data/chores/runs/`. Es la base mas sana que ya existe.

## 5. Arquitectura propuesta (capas) y por que

El salto a "asistente" no viene de un modelo mas grande: viene de **bajar el numero de turnos
por tarea** y de **sacar la percepcion del loop**.

| Capa | Que hace | Pieza | Modelo que necesita |
|---|---|---|---|
| 0 Decision | donde piensa: 100% local vs hibrido | ver §7 | - |
| 1 Percepcion | saca hechos: titulos, remitentes, montos, coordenadas | DOM/CDP, UI Automation, OCR nativo, VLM bajo demanda | ninguno (o VLM puntual) |
| 2 Skills | un script determinista por tarea, idempotente, con estado en disco | nuevo, patron de `chores_api.py` + `queue.json` | ninguno |
| 3 Driver | elige skill, arma argumentos, redacta texto | omp + modelo local | 1 slot |
| 4 Manos | ejecuta | ZCode computer-use (regla del usuario) y/o MCP browser propio | el loop de ZCode (nube) |
| 5 Aprobacion | journal + "aprobar <id>" + dry-run siempre | nuevo, chico | ninguno |
| 6 Memoria | lectura cada turno, ingesta en ocioso | supermemory :6767 | 1 slot ocioso |
| 7 Voz | responde en audio | TTS local (ya); STT local opcional | GPU para STT |

Motivo de la division 1/2: el driver local no es confiable guiando el browser paso a paso
(§6), pero es bastante bueno eligiendo una skill y redactando. Si la percepcion ya viene hecha
y la accion es un script, la confianza sube mucho y el tiempo por tarea cae de 15-30 min a
segundos.

## 6. El cuello de botella, cuantificado con lo medido en la caja

- Turno de agente con tools ≈ 30-60 s a 36 t/s (NeoHorse 4B) -> una tarea de 30 turnos =
  **15-30 min**. Con Bonsai-2 27B (13 t/s) es 2-4x peor, y con ctx 8K ni entra el system
  prompt de omp (~21.4K tokens, medido 09-23) -> **Bonsai-2 no puede ser el driver de omp** sin
  el proxy compresor; sirve como revisor de una pasada.
- Rankings como driver (con lo medido): **NeoHorse 4B** (32K, tool calls nativos 3/3, 36 t/s, el
  mejor agente chico de la caja) o **Qwen3.5-9B** (32K validado, 30-33 t/s, mejor en codigo,
  tools ok). Si hay que elegir uno solo para el loop: 4B por latencia, 9B por confiabilidad.
- Todo lo de 27B+ = revisor bajo demanda (una pasada, no un loop). `stall_watchdog.py` ya
  demuestra el patron: cuando el local se traba, un revisor grande en OpenRouter resuelve.
- Con Vision (Qwen3-VL-4B) el driver puede *ver* cuando el DOM no alcanza; el costo es que VLM
  y driver **no pueden convivir** (GPU exclusiva). Decision pendiente: un mismo proceso con
  vision, o dos arranques conmutados.


## 7. Fases (esfuerzo y dependencia de GPU)

| Fase | Que | Esfuerzo | GPU |
|---|---|---|---|
| **F0** | Arreglar el path local de la API (hallazgo 1) + dejar el smoke test listo | 30-45 min | no |
| **F1** | **Eval del driver**: 3 tareas reales x 2 modelos (NeoHorse vs Qwen3.5-9B), midiendo turnos, tiempo, reintentos y fallos. Script nuevo al estilo de `scripts/minicpm_tool_probe.py`; nada de descargas | 1-2 h | si, 1 slot |
| **F2** | **Capa de skills**: 4 scripts deterministas + journal + `aprobar <id>`. Empezar por los 2 de `TASKLIST` (outreach CV&L, contestar mensajes) | 1-2 dias | no |
| **F3** | Validar el VLM en Vulkan (`tmp/vl_smoke.ps1`). Si el grounding falla, `Holo1.5-3B` (~2.9 GiB) | 15 min / +1 h | si, 1 slot |
| **F4** | STT local (whisper.cpp `small` ~500 MB o sherpa-onnx) para sacarle Deepgram | 1 h + descarga | parcial |
| **F5** | Memoria como tool MCP de solo lectura en el turno; ingesta programada en ocioso | 3-4 h | no |

Orden recomendado: F0 -> F1 (con la GPU libre) -> F2. F3 depende de que F1 diga si el driver
necesita ver; F4 y F5 son mejoras, no prerrequisitos.

## 8. Riesgos (con su mitigacion)

1. **Inyeccion de prompt**: contenido de correo/web + `--auto-approve` + bash/files. Mitigacion:
   el driver nunca ve HTML crudo como instruccion (percepcion extrae datos, §5), sin bash,
   dry-run y aprobacion humana antes de cualquier accion irreversible.
2. **LinkedIn**: la propia regla del usuario es "ritmo tranquilo y discreto, no nos queremos
   comer un ban". Limite duro de frecuencia, cuenta propia, nada de scraping masivo, y el
   borrador lo confirma una persona.
3. **Dinero / 2FA**: nunca guardar credenciales; reusar la sesion del perfil dedicado del
   navegador; confirmacion humana siempre para pagos.
4. **`yolo`**: bajarlo a `confirm` para el asistente (el yolo puede quedar solo para coding).
5. **Disponibilidad**: la ventana 23:30-07:30 la ocupa `llama-server-evening` + campana; el
   asistente no puede ser daemon ahi. Decidir si vive en esa ventana con el server ya loaded o
   si se apaga.
6. **RAM**: la campana exige 11 GB libres; cualquier resident de 9B hace que se salten slices.

## 9. Decisiones que son del usuario

1. **Local puro vs hibrido.** Local puro = privado y gratis, pero 15-30 min por tarea de browser
   y todo el riesgo de alucinacion quedalocal. Hibrido (local redacta/percibe, la nube ejecuta el
   loop riesgoso) es lo que ya hacen hoy con ZCode. ¿Cual se quiere?
2. **Un solo driver o dos** (4B por velocidad, 9B por confiabilidad) — y si el VLM comparte slot
   con el driver o va conmutado.
3. **Aprobacion**: ¿por envio, por tanda, o solo lectura automatica?
4. **Alcance de la primera skill**: ¿ outreach CV&L, o contestar mensajes de laburo? `TASKLIST`
   lista las dos; una sola primero, medible.

## 10. Que NO se hizo (declarado)

- **Cero modelos corridos**: la GPU es de otro. El VLM esta instalado pero sin smoke test.
- **Cero descargas nuevas**: solo los 2 artefactos de Qwen3-VL (los unicos permitidos, para el
  pedido de vision); las alternativas quedan documentadas con numeros.
- **No se toco** `SESSION_CONTEXT.md`, `HANDOFF_2026-09-25.md`, `night_*.ps1`, ni
  `C:\src\llama.cpp`. El bloque que se habia puesto en `SESSION_CONTEXT.md` quedo **revertido**
  y su contenido vive en §3 de este doc.
- **No se crearon tareas programadas** ni se tocaron puertos/servers.
- Escrito unicamente en: este doc, `data/models/qwen3vl-4b/**`, `tmp/vl_*`,
  `scripts/local_models.py` (+ test), y la linea de claim en `BRIEFS/CLAIMS.md`.

## Resultado (2026-09-25)
- Modelo de vision local **elegido, bajado y verificado por hash** (Qwen3-VL-4B, arch `qwen3vl`,
  puerto 9112, `--mmproj` soportado, test verde). Smoke test pendiente de GPU.
- **Eval del asistente personal**: inventario verificado de las 8 capas que ya existen, **9
  bloqueos con archivo/linea**, arquitectura en capas, el cuello de botella cuantificado
  (15-30 min/tarea de browser con el mejor driver local), 6 fases con esfuerzo, 6 riesgos y
  4 decisiones que son del usuario.
- Correccion importante respecto a la propuesta anterior: **el correo no va por IMAP** (regla
  fija en `TASKLIST.md`: todo envio por ZCode computer-use). El eval lo respeta.

