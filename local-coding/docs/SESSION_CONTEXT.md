## Laya janitor + stall watchdog (2026-09-24): HECHO, 26/26 tests
- Idea del user (madrugada: spark murio con "compression error"/HTTP 400 en omp):
  (1) un mini janitor que limpie/corte el contexto para que esto no pase;
  (2) si el modelo no tickea en X tiempo, un modelo mas grande despierta a revisar.
- Janitor: `compress_messages` de bonsai2_proxy.py YA NO colapsa el historial a un
  solo mensaje user (ese pendiente viejo de roles rotos en uso agentico queda
  cerrado): conserva el system head, resume SOLO el medio viejo via el modelo,
  conserva la cola reciente con sus roles (incl. pares assistant tool_calls/tool),
  fija el ultimo turno de usuario y cae a `_hard_truncate` si el resumen no cabe
  o el modelo falla. 5 tests nuevos en test_bonsai2_proxy.py.
- Watchdog: scripts/stall_watchdog.py + STALL.cmd. Vigila el log del modelo
  (default = BOT_MODEL.txt / spark): alarma `context-overflow` (lineas nuevas
  "exceeds the available context size"), `stalled` (task en vuelo sin ticks en el
  log por --stall-secs, default 120s) y `server-down` (state.json lo lista pero el
  puerto no responde). Al disparar arma un dossier (cola del log + ultima pregunta
  de la sesion omp + health) y lo manda a un revisor grande en OpenRouter gratis
  (default `openrouter/free`; clave OPENROUTER_API_KEY de ~/.omp/agent/.env) con
  DIAGNOSIS/FIX en <=150 palabras; veredicto en data/stall_watchdog/reviews/.
  Cooldown 600s por motivo; primera pasada solo siembra. 13 tests en
  tests/test_stall_watchdog.py. STALL.cmd --once sale 3 si disparo.
- Nota de diseno: el revisor es cloud (no local) porque la GPU es exclusiva: no se
  puede levantar un modelo grande local mientras el vigilado ocupa la VRAM.
- Suite completa verificada: 121/121 OK en ~74 s (la primera corrida tarda porque
  hay tests con sondeos/modelos). `STALL.cmd --dry-run --once` con spark en vivo
  responde silencioso = sin alarma (log con tasks liberados).

## OMP contra el servidor vivo (2026-09-23): ARREGLADO y verificado E2E
- Sintoma del user: en `omp` (oh-my-pi 18.2.8) "Unable to connect. Is the computer able to
  access the url?" mientras el hub decia NeoHorse ENCENDIDO en :9107.
- Causa: `~/.omp/agent/config.yml` tenia `modelRoles.default: smol/neo`, que apunta al slot
  Smol `:9104` — y ahi no escuchaba nadie (netstat: solo :9107, llama-server PID 62428).
  El :9107 estaba sano: /health ok, alias `neohorse`, n_ctx 16384, ~31 tok/s.
- Segundo desajuste resuelto por otra sesion a las 10:35 (ver git diff de local_models.py): el
  provider `neohorse` y el server tienen que coincidir en contexto. El motivo real de subir el
  server de 16384 a 32768: OMP manda ~21.4K tokens SOLO de system prompt + esquemas de
  herramientas, o sea que a 16384 toda sesion con tools muere con HTTP 400 aunque el usuario
  escriba una linea. Estado final 10:36+ : :9107 with `-c 32768` (health ok, Vive en 8 GB con
  KV q8), `local_models.py` y `start_neohorse.ps1` los dos en 32768, y el provider de omp en
  contextWindow 32768.
- Arreglo mio (10:16): `default: neohorse/neohorse` en `~/.omp/agent/config.yml` (antes
  `smol/neo` = :9104 muerto); provider `neohorse` con maxTokens 3072, `reasoning: true` y compat
  {reasoningContentField: reasoning_content, maxTokensField: max_tokens,
  supportsReasoningEffort/Store/DeveloperRole: false}.
  Backups: `~/.omp/agent/config.yml.bak-20260923-neohorse-default` y
  `models.yml.bak-20260923-neohorse-ctx`. `config/local-omp/models.yml` (perfil Taller) sin cambios.
- Verificado: `omp -p` sin `--model` en Z:\catts devolvio texto real (TCP omp->:9107 ESTABLISHED).
  Sondas crudas en `tmp/probe_neohorse_ids.py` y `tmp/probe_neohorse_turns.py`: id de modelo
  distinto ("neo") igual se acepta; T1 simple OK; T2 historial sin reasoning_content OK;
  T3 tool_calls nativos OK; T4 vuelta tras tool OK.
- Trampa del modelo: NeoHorse-1 4B es de razonamiento (emite `reasoning_content`); con
  max_tokens corto (32) gasta todo pensando y deja `content` vacio -> parece que "no responde".
  Por eso maxTokens 3072, no 2048/32.
- Medidas del server (tmp/probe_neohorse_prefill.py): prefill ~540 tok/s (2.2K prompts 544,
  7.1K prompts 537), decode ~31 tok/s. Con el server a 16384 un prompt de >16K da HTTP 400 —
  justo lo que le pasaba a OMP con tools. El "Working..." largo de omp NO es prefill: es la
  cadena de razonamiento del modelo (turno simple ~65 s; turno con herramienta read via omp
  ~4-5 min, pero completa). Con `-np 1` los clientes concurrentes se encolan y el KV se rehace:
  no lanzar sondas mientras el user esta en sesion.
- Cambiar de modelo EN la sesion omp: `Alt+P` (temporal para esta sesion) o `Alt+M` (picker);
  `Ctrl+P` cicla. Ojo: reabrir con `omp -c` (resume) reusa el modelo viejo de la sesion; para
  estrenar el default hay que abrir una sesion nueva (`omp`).
- Pendiente: una sesion omp ya abierta no cambia en caliente (la del user sigue titulada
  "Smol NeoHorse 4B" = smol/neo = :9104) -> Alt+P / Alt+M a `neohorse`, o abrir una sesion
    nueva. Supermemory (:6767) estaba DOWN, asi que no se registro la leccion.
- RECAPI (2026-09-23 14:xx): el user volvio a caer en overflow ("compression error") porque el
  provider que resolvia era `smol/spark` (:9104) que SIGUE etiquetado 16 K aunque el server vivo
  es minicpm a 32 K: Otra vez 21.4 K de system+tools + payload > 32 K -> HTTP 400. Ademas MiniCPM5
  2B codigo = 3-4/12. Solucion: pasar a `spark/spark25` (:9105) con `-c 65536` (balanced preset).
  - `local_models.py` spark args usaban `-device` (single dash) -> bug -> server no arrancaba; arreglado a `--device`, contexto base 16384 -> 65536.
  - `~/.omp/agent/models.yml`: minicpm5 131072 -> 32768 (verdad :9104 mini); `smol/spark` 16384 -> 65536 + maxTokens 8192 + compat supportsReasoningEffort:false; `spark/spark25` maxTokens 2048 -> 8192 + compat reasoning_effort false. Archivo YAML validado (safe_load OK).
  - `~/.omp/agent/config.yml` se habia borrado tras el primer intento de edicion (indentacion rota -> omp lo reseteo); reescrito valido con `modelRoles.default: spark/spark25`.
  - Verificado E2E: `curl POST /v1/chat/completions spark25` a :9105 -> 200 (motivo `reasoning_content` presente, no 400). Log previo de spark: task 50300 con 44639 tokens en contexto, truncated=0 (64 K de verdad).
- Para el user: CERRAR la sesion omp actual (todavia resuelve smol/spark 16 K) y ABRIR UNA
  sesion nueva. omp leera config.yml -> default spark/spark25 -> barra "Spark-X2.5 4B (9105) 64 K".
  Decir "hola" -> responde sin 400 ni compaction loop. Thinking: Ctrl+T toggle, Shift+Tab cicla nivel,
  Alt+P cambia modelo. Spark NO usa reasoning effort server-side como qwen27; con `--thinking off` ahorra tokens si no quieres cadena larga.


## Propio portal como app Edge (2026-09-19): HECHO, USER-INSTALLED
User (intérprete de video) quería app desde Edge para https://interpreters.propio-ls.com/portal (Edge le rinde mejor que Chrome en video). Hallazgos: pake-cli 3.16.4 ya instalado global (+ cargo 1.96.1, node 22.12); Pake en Windows = Tauri WebView2 = MISMO motor de Edge (Edge 153.0.4234.32 y WebView2 153.0.4234.32 verificados en C:\Program Files (x86)\Microsoft\EdgeWebView) - video/hw-decode idénticos a Edge, no Chrome. Portal SIN manifiesto PWA (login shell JS plano). Sin políticas Edge que oculten opciones (HKLM\SOFTWARE\Policies\Microsoft\Edge no existe). Alternativa usada: Edge ⋯ → Apps → "Instalar este sitio como aplicación" - usuario la ejecutó y FUNCIONA; no se compiló nada con Pake. Descartado Nativefier/Electron (Chromium viejo embebido, no evergreen Edge). Carpeta Z:/catts/local-coding/pake-apps creada por si se quiere un build Pake después (primera compilación ~5-10 min). Sin cambios en repos/modelos.


## Hub de modelos: un solo terminal (2026-09-19): READY, sin ventanas extra
User asked: un solo lugar para ver/arrancar/cambiar/apagar modelos, sin "tons of cmd".
Hecho: Z:/catts/local-coding/CATTS.cmd + scripts/hub.py (menu interactivo: s N start,
w N switch, x N stop, a stop-all, c N chat directo, l N log, z N que elegir en Zed,
t/m sesiones Taller/Smol) + scripts/local_models.py como UNICA fuente de verdad
(modelos, puertos, alias, runtime por modelo, presets mid/low/high, pisos de RAM);
smol.py ahora importa ese registro (MODELS/RUNTIMES/PRESETS/server_args delegados,
sin duplicar valores). Apps incluidas: CATTS API :59200 (ya estaba arriba, el hub la
detecta), Chores :9111, gateway de voz :9110. Todos los hijos van con CREATE_NO_WINDOW
y log en data/hub/logs; no hay `pause` encadenado ni ventanas nuevas. El hub ADOPTA
servidores ya arrancados (identifica por puerto/alias/ruta: Bonsai-2 PID 10092 :9103
aparece ENCENDIDO) y no toca desconocidos. GPU exclusiva: start se niega si hay otro
modelo arriba (switch apaga y espera liberacion de VRAM). Validado: hub.py check 0
problemas (19 entradas), list/status OK, chat contra :9103 respondio HUB_OK, ciclo
start/stop de app probado (voicegw :9110 escuchando -> detenido), tests.test_smol 8/8 OK.
Pendiente/limitacion: no se probo un start de MODELO real en vivo porque :9103 estaba
en uso por el usuario (Bonsai-2); el proximo switch lo ejercita. Desktop: instalado
"CATTS local.lnk" (scripts/install-hub-shortcut.ps1). Zed sin cambios (ya tenia los
providers); el hub dice que provider/model elegir para el modelo que este arriba.

## MiniCPM5-2B Q8 @ 131K hand-use coding server (2026-09-18): READY, USER-LAUNCHED
Built Z:/catts/local-coding/MINICPM5-CODING.cmd + scripts/start_minicpm5_coding.ps1
(port 9104, -ngl 99, -c 131072, q8 KV, fa, jinja, temp 0.2, alias minicpm5-coding,
RAM floor 3 GB, VRAM advisory warning). Model minicpm5-2b-q8/MiniCPM5-2B-Q8_0.gguf
2.5 GB SHA-verified. LIVE-VALIDATED at -c 32768 while user's :8123 Qwen3.5-9B held VRAM:
health 200, chat completion OK. Two findings: (1) MiniCPM5 defaults to thinking mode -
default probe returned 20 hidden <think> tokens + empty content; launcher pins
--chat-template-kwargs '{"enable_thinking":false}' which gave clean "READY"/3 tokens;
(2) 131K FULL ctx needs ~7 GB VRAM alone - user must close :8123 first or drop -c to
65536 (both documented in launcher). Probe server stopped; :8123/:9102-class servers
untouched; no model/runtime changes. Caveat stands: MiniCPM failed coding-quality gate
2026-09-16 (3-4/12) - hand use OK, not promoted to project editor.

## Bonsai-2 Colab CUDA hookup (2026-09-18): NOTEBOOK READY, UNTESTED IN CLOUD
User asked to run Bonsai-2 in the cloud. Built Z:/catts/local-coding/docs/colab/bonsai2_cuda_colab.ipynb
(6 code cells, JSON-validated, all compile) + BONSAI2_COLAB.md quickstart. Verified facts:
Prism fork ships PREBUILT Linux CUDA binaries (release prism-b10687-5d80cff, 2026-09-17;
assets llama-...-bin-linux-cuda-12.4/12.8-x64.tar.gz) — no compiling needed; model =
prism-ml/Ternary-Bonsai-2-27B-gguf, PTQ1_0 = 5,946,648,928 bytes (matches local copy),
ctx 262144, tokenizer embedded in GGUF. Notebook flow: nvidia-smi build pick, tar prebuilt
server, hf_hub_download, server -ngl 99 -c 16384 -fa on + optional --api-key, 2-prompt
bench (enable_thinking=False), cloudflared tunnel URL printed for local agent wiring
(base_url <url>/v1). User executes it (Google login is theirs); expectations T4 5-15 tok/s
vs 3.3 local Vulkan. NOT executed in Colab (no account access); no local downloads/runtime
changes; scratch generator deleted after validation.


## Bonsai-2 27B PTQ1_0 tested (2026-09-18): RUNS-ONLY-ON-PRISM-FORK, SLOW
User asked to try Bonsai 2 coding speed. Full offload now fits (ngl 99, 8K ctx q8 KV,
~97 s HDD load; 9.6 GB free RAM). Speed probe: decode 3.3 tok/s, prompt 40-65 tok/s —
not the ~28-130 tok/s from the model card; those figures are CUDA/Metal. Prior 09-17
attempts at ngl 40/60 were 1.2 tok/s (partial offload). Runtime A/B: mainline Vulkan
b10964/b10828 and demo-bin b9591 all REJECT the GGUF (custom ggml type 143 packed
ternary); only Z:/Models/runtime/llama-prism-b10685-vulkan loads it. Mainline support
does not exist for PTQ1_0 (card confirms kernels are fork CUDA/Metal only). Quality
2-turn probe (read then write toCents): 2/2 clean native tool calls, correct code,
no loops, thinking off works. Verdict: tool mechanics PASS, unusable speed on this
rig (Vulkan fork has no packed-ternary kernels). User self-try setup: BONSAI2.cmd +
scripts/start_bonsai2.ps1 (ngl 99 pinned, 9103, RAM floor 3 GB, sampling from old
bonsai defaults). Trial servers stopped; pre-existing PID 7824 :8123-class server
untouched. No runtime/download/model changes.
## Bonsai-2 speed + local long-context Q&A (2026-09-18)
Q1 speed fix: NO quick fix on this rig. PTQ1_0 type-143 packed-ternary kernels are
fork CUDA/Metal only; no Vulkan implementation exists in Prism fork and no mainline
merge as of 2026-09-18. Demo repo's "mainline Vulkan merged" refers to Bonsai-1
Q1_0/Q2_0_g64, not Bonsai-2. Repo has only PTQ1_0/PQ2_0 + mmproj (no g64 variant).
Real fix = NVIDIA/CUDA GPU or Prism shipping Vulkan kernels. User self-try stands.
Q2 long-context installed models (GGUF metadata verified): Qwen3.5-9B 262K native,
32K validated ~30-33 tok/s ~5.4 GiB; MiniCPM5-2B Q8 131K native, 48-60 tok/s, ~3.0
GiB at 32K, 131K plausible with one probe; Coder-7B 32K native; Gemma12 262K but
0/3 tools; 27B consultant 262K at 7 tok/s; Spark 1M native UNTESTED; NeoHorse 262K
UNTESTED; Qwen3.5-4B 262K host tests 4/12. Nothing validated past 32K on rig.
Recommended long-doc agent: Qwen3.5-9B (32K today); probe candidate: MiniCPM5-2B
at 131K. Notes file: Z:/catts/tmp/bonsai2_speed_ctx_notes.json.

## MiniCPM5-2B "code able" evaluation (2026-09-16): FAIL at gate
User asked to make MiniCPM code-capable in SMOL; approved probes + repair trial.
OMP tool probes 4/4 PASS (16K/32K x default/xml): real `read` toolCall + successful
result each; XML template unnecessary (initial "prose_only" summary was a parser
bug counting `toolcall` vs `toolCall`; raw logs untouched, hash-verified, parser
test added). Checkout test-feedback trials (existing runner, temp 0, 3 test runs,
isolated hash-guarded fixture): trial 1 = 3/12, trial 2 = 4/12; repairs touched
only money.cjs; cart ReferenceError, receipt missing import, cents formatting and
shipping threshold persisted through both feedback rounds. Tool mechanics fine
(~50-60 tok/s, no loops); failures are code quality. GATE: not promoted; qwen35
stays project editor; no more MiniCPM coding trials without new evidence.
Report: docs/MINICPM5_REPAIR_TRIAL_2026-09-16.md. Evidence under data/smol/probes/
and data/minicpm5*-project-20260916-*/. minicpm_trial_guard.mjs drafted but
UNVALIDATED (scratch). Host tests 32/32; servers stopped; SMOL defaults unchanged.

## K2-Horizon-7B assessed (2026-09-16): DEFERRED — watch-list
User asked "eval worth?" on an @IFM_AI post. Verified via HF model card, GGUF repo
and llama.cpp discussion #28308: Apache-2.0, fully open, dense 7B-core (9.00B stored
incl. 250K vocab), 512K native context. Author tables: SWE-bench Verified 70.6 vs
Qwen3.5-9B 50.8; Terminal-Bench 2.1 39.1 vs 29.2. AA Intelligence Index 21 is real
but generated 160M tokens vs 76M median — score partly bought with verbosity.
BLOCKERS on this rig: no mainline llama.cpp (MBZUAI-IFM fork only, PR in progress);
GGUF requires fork = new runtime (our Vulkan builds stay mainline); trust-remote-code
custom arch. Counter-testimony: user report worse than NeoHorse/Ornith-1.5-9B in
practice. RE-EVAL TRIGGER: mainline llama.cpp merge + independent SWE-bench
replication. Cheaper unexplored candidate remains Ornith-1.5-9B (installed, 0.5 GB
incomplete download flagged by --check inventory). Next coding eval unchanged:
test-feedback repair-loop trial on installed models. No download/trial authorized.

## Next task: ZDTaichu5.0-9B assessment (queued 2026-09-16)
User supplied a David Hendrickson (@TeksEdge) post, September 16, 2026.
Candidate: TaichuAI/ZDTaichu5.0-9B. Claims below are from the supplied post,
NOT independently verified and NOT local measurements.
Qwen3.5-9B language backbone + NVIDIA C-RADIOv4-H vision encoder; image/video,
spatial reasoning, embodied/tool use, any-resolution vision, 128K context.
Entropy-Gated Adaptive Recurrent Reasoning reportedly adds latent refinement
only for difficult tokens. Author-reported scores (candidate / Qwen3.5-9B):
ViewSpatial 62.5 / 48.2; MindCube-tiny 78.3 / 57.6; TAU2-Bench 87.7 / 79.1;
LiveCodeBench v6 73.4 / 65.6. These do not establish repository-edit reliability.
Post claims Transformers custom code, custom TaichuAI vLLM fork and Docker;
no mainline llama.cpp, GGUF, LM Studio or MLX at posting time.
Next: verify primary model card/license/code, recurrent architecture and text-only
inference path; determine RX6600 8GB / Windows Vulkan compatibility and memory.
Single-GPU/OpenAI-compatible API does NOT establish compatibility with this rig.
No download, custom-code execution, runtime migration or model trial authorized
by this queued note. Keep installed MiniCPM/Qwen workflow as baseline.

## SMOL repair + offline/tuning pass (2026-09-10): DONE
User task: make downloaded models dead-simple offline; tune so simple edit requests perform edits.
smol.py had a regression after 2026-09-07: the whole launch block sat indented inside the low-RAM
guard after the raise (server start unreachable on healthy RAM). Repaired; smoke PASS.
scripts/probe_load.py measured all 7 models: load + generate OK at 32K (KV q8_0, full offload,
8 GB VRAM). 32K is now the default (Nanbeige 16K default: 6.7 GB VRAM at 32K). --no-mmap restored
with measurements: Z: is an HDD (~34 MB/s sequential; mmap ~2x slower; peak RSS 876 MB with a 5.7 GB
model — the old 3 GB RAM-guard premise was wrong for full offload). Per-model RAM floors:
E4B 2.8 GB (keeps 1.9 GB host embeddings), Gemma12 1.8 GB, rest 1.5 GB. Qwen3.5-9B +
Qwen2.5-Coder-7B added to the SMOL menu from Z:/Models/coding via new register_local_model.py
(local sha256 manifests). --check now inventories every GGUF on Z: (flags 27 GB orphaned Ollama
blobs, duplicate Qwen2.5-Coder in Z:/AI/models = the 8123 prior server's file, 0.5 GB incomplete
Ornith-1.5-9B-Official; deletes nothing). TALLER: 9102 ctx 8K→16K, --no-mmap + --cache-reuse,
RAM floor 2 GiB for the 9B (27B consultant keeps 6 GiB, partial offload). local-work.ps1 now
refreshes models.yml every run (a stale 8K/2048 copy survived at E:/.../data/local-omp) and passes
new config/local-omp/limits.json (read 250 lines, keepRecent 3000); e4b profile maxTokens 2048→4096.
Tool-first system prompts (make the edit in-turn; never paste instructions; stop after two identical
tool failures). New smol_loops.py flags 3+ identical calls / failing turns post-run.
Fixture edit-smoke (smol_fixture.py, 32K): qwen35 PASS (move-div, self-corrected first edit,
6.6K tokens), coder7 FAIL (emitted the edit call as ```json text, hallucinated index.html) →
SMOL.md now recommends qwen35 for project work. 24 host tests PASS. No downloads, no runtime
change (MTP/Spark stay blocked). Servers stopped; probe/fixture evidence under
data/smol/probes/ and data/smol/fixture-runs/.


## LOCAL CODING PLAYBOOK (2026-09-10): WRITTEN
User asked for every-conceivable-level investigation; research-only, no changes made.
Deliverable: LOCAL_CODING_PLAYBOOK_2026-09-10.md. Headline: failures are harness/quality
not capability (FrogNano 8.3→37.2 harness evidence; mini-SWE-agent 65% in 100 lines);
prioritized: loop-detection > runtime update > patch-apply/lint > best-of-3 > constrained
tools > Spark/MTP/Ornith trials > Unsloth-Vulkan training check (unverified) > FrogNano watch.
All actions await explicit user OK at run time.


## KIMI K3-in-C assessed (2026-09-09): REJECTED
User-asked assessment only; no download/run. 2.78T CPU-only, disk-streaming C99 engine
(Apache-2.0): no GPU path, 1.56TB custom non-GGUF checkpoint, ~20-30 s/token on far stronger
rigs (disk-bound; slower here). Opposite of the smaller-model/use-GPU goal. Ideas noted in
KIMI_K3_IN_C_ASSESSMENT_2026-09-09.md.


## Qwen3.5-4B base trial + FrogNano eval (2026-09-08): DONE
User authorized a trial after the FrogNano report (PDF at Z:/catts root; extract in temp).
FrogNano (MS Froggy, 4B RL, 61.5% SWE-bench Verified) is NOT released: debug-gym page + all 538
microsoft HF repos checked; only FrogBoss/FrogMini. Report facts: base Qwen3.5-4B + Leaf-style
harness = 43.0% at 131K; compaction recovers full perf at 64K (32K: fires in 51% rollouts);
Leaf tools = read/write/edit/glob/bash (smol-shaped). NeoHorse report queued for later:
https://github.com/TokenRhythm/NeoHorse/blob/main/TechnicalReport_NeoHorse_v1.pdf
Trial: verified Qwen3.5-4B Q8 (bartowski, sha256 in manifest) via existing
bonsai_project_trial.py; 5 turns/33s, tools PASS, 5 parallel reads, natural stop; host tests
4/12 (below MiniCPM 5/12, E4B 6/12, Bonsai 7/12). One deviation: --no-mmap removed from trial
server args (4.6GB load stalled with 5GB RAM; mmap loads in 15s). 24 host tests + smol:check
PASS. See QWEN35_4B_PROJECT_TRIAL_2026-09-08.md. No promotion; servers stopped. Re-run the same
trial if a FrogNano GGUF appears.

## QUEUED (2026-09-08 evening): Spark trial + Bonsai Ternary + MiniCPM tool-repair notes
User busy; deferred. RAM cap going forward: do not assume >~8GB free system RAM (user's words),
prefer mmap loads, avoid --no-mmap for >4GB models.
1. Spark-X2.5-4B trial AUTHORIZED PLAN (pending run): candidate is legit (SWE Pro 44.4 > 9B's
   33.8; agentic benches near-9B; Verified 41.6 ~= base 4B; all scores thinking-mode temp1.0).
   4B Q8 fits VRAM, SWA hybrid keeps KV small, ~40-50 tok/s expected. BLOCKER: our Vulkan
   runtime build 10516 predates spark2_5 (llama.cpp b10828 2026-09-07; bundled builds error
   "unknown model architecture"). Plan: install official b10828+ Windows Vulkan release OR build
   XHToken/llama.cpp fork with -DGGML_VULKAN=ON (fork Vulkan-tested), then verified Q8 download
   from XHToken/Spark-X2.5-4B-GGUF and bonsai_project_trial.py run (try thinking-off AND
   thinking-on variants). Runtime addition = needs explicit user OK at run time.
2. Bonsai-27B TERNARY (prism-ml Q2_0_g128, 7.17GB): SKIP for now. VRAM over 8GB -> partial CPU
   offload -> 27B-Q4-class speed; PrismML fork kernels CUDA/Metal only, no Vulkan; card admits
   agentic coding not targeted yet (roadmap variant is the one to watch). Two prior Bonsai 27B
   failures (7/12, 0/6) stand.
3. MiniCPM5-2B agent observation (external, for harness work): 12 runs, 6-step task, Q4_K_M,
   32K ctx on 8GB 3070: 214 tool calls, 21 malformed, 9 self-repaired, 12 human-fixed; 7/12
   finished, 5/12 died in repeat-loop (replays identical call on identical error string — quiet
   harness retries hide it). Implication for smol/OMP harness: add repeat-loop detection +
   ask-user or vary-hint on repeated identical failing calls. KV math: 131K = +5.2GB KV (won't
   fit 8GB); 32K total ~2.9GB. Weights 1.56GB.
Trials protocol unchanged. See QWEN35_4B_PROJECT_TRIAL_2026-09-08.md for latest rig baseline.

## 32K context + tool caps (2026-09-08): DONE/VALIDATED
User requested implementation of tool-output caps, per-model --context, and the 32K MiniCPM trial.
smol.py: `--context 16384|32768` (32K gated to mini, gate enforced in run()); CONTEXT stays 16384 default.
profile() writes limits.json overlay (OMP --config, deep-merged): read default 120 lines, artifact spill
>8KB keeping 2KB head/4KB tail (60 tail lines), bash capture 64KB, compaction keepRecentTokens 3000 (16K)/6000 (32K)
[OMP default 20000 exceeded the whole window]. agent_args always passes --config; overlay file is a hard error if missing, so profile() must run first (it does in run()).
Trial (data/smol32k-trial-20260908-101203/): 32K load 3.57GB VRAM; 23,878-token prompt recalled 3/3 exact markers;
OMP read smoke PASS at 32K; prefill ~79 tok/s (24K fill ≈5 min — binding constraint, NOT VRAM); decode ~33 tok/s at depth.
One real task (host-controlled tools, 1 test run, no repairs): FAIL, no tool calls — consistent with prior MiniCPM coding failures; no promotion.
Trial server stopped; no prior server was running; protected files intact (hash flag was a CRLF artifact, annotated in report).
24 host tests PASS; smol:check PASS (all 5 models). SMOL.md updated (--context, caps, results). No runtime settings beyond these.

## Large repo usage guide (2026-09-07)
SMOL.md now includes bounded JSX reading prompts, manual PowerShell extraction,
risks/remedies and the unimplemented 32K experiment. No runtime changes or trials.

## Smol in-terminal help (2026-09-07)
SMOL.cmd --docs or ? in menu reads docs/SMOL.md; --help lists CLI flags.
Guide includes Termius, workflow, context handoff, troubleshooting and RX6600 ideas.
Interactive context-choice guard remains NOT implemented; runtime settings unchanged.

## Personal model access (2026-09-07): READY
User requested direct personal use, no further coding trials.
Desktop Smol local / SMOL.cmd: Enter opens MiniCPM fast chat; numbered menu
offers5 installed models,chat/project,thinking,new/continue. OMP18.0.6 retained.
scripts/smol.py owns server9104 with Windows kill-on-close job,single-launch lock,
known Qwen8123 pause/restore on normal exit. Separate profiles/data/smol.
No trial time/token cap;max_tokens=-1,16K context,no context shift,auto compaction65%.
Project tools read/write/edit/grep/glob/bash;approval always-ask,Git Bash explicit.
24host tests PASS;all5model OMP replies+shutdown PASS;Mini project read PASS.
Final all model servers stopped. See docs/SMOL.md,data/smol/setup-validation.json.
Prior coding failures remain valid within their documented trial limits.

## Nanbeige test-feedback trial (2026-09-07): INCOMPLETE
Restricted run_tests added;12min/3 test runs/2 repairs allowed.
Read files then8192 reasoning tokens hit response limit at~389s API.
No edits/tests/repairs occurred;repair capability not evaluated. All hashes intact.
Servers stopped. See NANBEIGE_FEEDBACK_TRIAL_2026-09-07.md. No more trials.

## Nanbeige4.2 Q8 thinking trial (2026-09-07): FAILED/INCOMPLETE
Runtime/native tools/reasoning preservation PASS;21-25tok/s,16K.
Six-minute deadline during self-review. Wrote3 files;invalid regex blocks suite
loading (zero individual tests ran). Protected hashes unchanged;no repairs.
Q8 verified;launch-only legacy loop metadata overrides,no runtime change.
All servers stopped. See NANBEIGE_PROJECT_TRIAL_2026-09-07.md.

## MiniCPM5-2B Q8 trial (2026-09-07): FAILED coding
Official Q8 downloaded+SHA256 verified;existing Vulkan/native tools PASS.
Checkout5/12 original tests,3 turns,19.75s API,~48-60tok/s. Multiple basic bugs.
Protected hashes unchanged;no repairs/runtime changes;all model servers stopped.
See MINICPM5_PROJECT_TRIAL_2026-09-07.md. Do not promote as project editor.

## Bonsai27B project trial (2026-09-07): FAILED
One authorized attempt:7/12 original checkout tests;9 turns,~103s API time.
Native API source-only tools,not OMP;16K,no MTP. Decimal/empty-cart bugs.
Protected hashes unchanged. No repairs. No prior server active;Bonsai stopped.
See BONSAI_PROJECT_TRIAL_2026-09-07.md. No reliable-project-editor claim.

## Later E4B/OMP project trial: FAILED
See E4B_PROJECT_TRIAL_2026-09-06.md. Dedicated E4B.cmd/npm e4b access prepared,
experimental only:16K, no MTP, isolated profile, write approval, no shell/subagents.
8K run exceeded context;16K run wrote nothing; final retry changed protected tests.
Host evaluated generated source against verified original tests in another copy:6/12.
Do NOT promote E4B to routine editor based on earlier3/3 toy tools. No more repairs.
19 host tests/check/syntax pass. All trial servers stopped; Qwen2.5 restored healthy
PID9468 on8123. User apps untouched. Pause/restore authorization persists for this task.
## Completed authorized solo trials (later 2026-09-06)
See SOLO_CANDIDATE_RESULTS_2026-09-06.md for evidence and limits.
E4B QAT:41–42tok/s, cross-file PASS, native tools3/3; best preliminary candidate.
E4B+MTP:50.8tok/s in ONE smoke only, agent flow not tested with MTP.
Bonsai27B Q1:16.7tok/s, tools3/3, cross-file code PASS after stripping Markdown.
Gemma12B Q3:18.4–18.5tok/s, cross-file PASS, tools0/3 (prose instead of calls).
All three baseline models passed ~6.5K-input marker probe in 8K context.
Small Python fixtures only; no reliable unattended-project claim or 128K validation.
Models+drafter downloaded and SHA256 verified. Prior Bonsai0/6 was 4B, not27B.
User authorized pausing :8123; Qwen2.5 restored healthy PID1480 with same args.
Task servers stopped; no profiles/defaults/runtime changes. Earlier1.4tok/s Gemma
result invalid due concurrent GPU use. Previous paused handoff below is historical.
# Local coding — compact handoff, 2026-09-06

User spent ~80% of weekly budget seeking reliable local coding. Experiments PAUSED.
Recommendation accepted: preserve remaining budget for concrete project fixes.
No claim of reliable unattended coding; do not restart trials from old handoffs.

Hardware: Ryzen5 PRO4650G, RX6600 8GB,16GB RAM. Models/runtime already on Z:.
Installed27B works around6.8–7.5tok/s but failed real cross-file Rosario edits.
Bonsai is fast; later exact-edit trial0/6. Earlier isolated success did not reproduce.
Ornith9B is INSTALLED BUT UNTESTED; tested Qwen3.5-9B is a different model.
ISTA IQ2_XS-MTP verified; tiny JSON smoke passed but1.42tok/s in tested52-layer profile.
No model/default changes. Task-owned models stopped at handoff.

Rosario trial: initial attempt +two repair rounds FAILED. Original1706 files unchanged.
Only isolated BottomNav changed. Final batch rejected atomically; do not promote.
Read ROSARIO_TRIAL_2026-09-06.md only when investigating that trial.
Raw evidence stays E:/zengatrivi-drive-e/catts/data/rosario-bottom-bar-20260906/.
Relative evidence filenames in the copied report refer to that directory.

Workspace split: Z:/catts/local-coding is the new documentation/work entry point.
Coding source/config migrated here; E: commands forward here. Shared Python/private OMP profile
and historical evidence stay on E:. 19 host tests pass on both entry paths. See SPLIT.md.
E:/zengatrivi-drive-e/catts is the active TTS workspace. Avoid its broad archive.




Standing user preference (2026-09-18): answer in layman terms, 40-80 words per reply.

## NeoHorse-1-4B Q8 first trial (2026-09-18, user-requested): PASSES tool use at 36 tok/s
Model Z:/catts/local-coding/data/models/neohorse14b-q8/NeoHorse-1-4B-Q8_0.gguf (4.17 GB, SHA manifest present).
Mainline Vulkan b10964, --device Vulkan1, -ngl 99, -c 16384, q8 KV, fa, no-warmup. Load 88.6 s from HDD.
Server-side: decode 36.1 / 37.1 / 37.3 tok/s (26.8-27.7 ms per token); prefill 18-192 tok/s (tiny prompts).
Native tool call PASS (read_file AGENTS.md, no prose); toCents JS code correct on the first try.
Bench: scripts/bench_model.py (new, generic) -> data/neohorse4b-bench.log. Server stopped after the run.
No promotion claim yet: one smoke, no project-edit trial, no long-context test.
Also: Bonsai-2 PTQ1_0 -> TQ2_0 conversion completed (data/models/bonsai2-27b-tq2_0/, 6.48 GiB, 2.07 BPW,
373 s); its speed A/B is PAUSED at the user's request. Conversion plan warning: default TQ2_0 plan promotes
token_embd/output.weight to q4_K/q6_K (7674 MiB total); force --token-embedding-type TQ2_0
--output-tensor-type TQ2_0 to get 6622 MiB.
New lead: Prism fork releases include bin-win-hip-radeon-x64.zip and bin-ubuntu-rocm-7.2-x64.tar.gz
(plus win/ubuntu vulkan) - a HIP/Radeon path for the RX 6600 is worth one test (gfx1032 not in AMD's
official ROCm matrix, so unverified). CatResumeMaker autostarts/tasks paused for the GPU window
(CatResumeMule, JobMule, llama-server-evening disabled; HKCU Run llama-server-autostart blanked,
original command kept in llama-server-autostart.disabled).

## Bonsai-2 TQ2_0 benched + promoted (2026-09-18 evening): 12-13 tok/s, 3.6x win
GPU-exclusive (Spark-4B stopped) TQ2_0 @ 8K q8 KV: decode 11.98-13.06 tok/s (3 probes), vs PTQ1_0 3.3. Quality PASS: toCents JS correct, find_dup trace correct (3, self-corrected). 100K ctx attempt = 3.2 t/s (KV q4 ~6.7GB pushes weights to CPU) - NOT worth it; physics cap ~34 t/s short-ctx, 100K ceiling ~3-5 t/s. start_bonsai2.ps1 updated to TQ2_0 model (still port 9103, ngl 99). AMD_CLOUD_VALIDATION_WORKFLOW.ps1 rewritten v2.0: mission is now ptq1_0.glsl LUT shader fix (~-25, 8-12h) not quant benching; v1 kept as _v1_OBSOLETE. Fork repo verified: github.com/PrismML-Eng/llama.cpp. Rig has NO build tools (cmake/glslc/cl absent) so shader fix is cloud-only. Test server left RUNNING on :9103 (PID 17916) for user hand-try. Spark-4B was STOPPED for the bench - user must relaunch if wanted.

Standing user preference (2026-09-18 evening): reply length capped at 3x the word count of the user's prompt. Supersedes the 40-80 word rule when stricter.

CORRECTION (user, 2026-09-19): Cline/Muse Spark used the wrong project folder (C:/catintassist) so Bonsai could not have performed the tasks against the real repo. Real project: C:/zengatrivi/REACTJS/catintassist. Do not retry from the stale C:/catintassist/work/repo copy.

## Overnight catintassist attempt (2026-09-19): 0/6, WRONG-PATH + Bonsai JSON ramble
Runner C:/catintassist/overnight.py + runner_lib.py + OVERNIGHT_TASKS.json (6 low-risk tasks) ran vs :9103 Bonsai-2 TQ2_0. All 6 MODEL FAIL: plan-call max_tokens 1200 too small for Bonsai's verbose reasoning (finish_reason=length, partial JSON discarded by design). Fix next time: max_tokens 2500+, ctx snippet cap 14000->6000, response_format json_object OFF (truncates: '{"pong": 1' observed), keep plain prompt + finish_reason guard. ALSO: user corrected path - real project is C:/zengatrivi/REACTJS/catintassist (298 src files, 103 tests, batch runner scripts/test-in-batches.js); runner had copied C:/zengatrivi/REACTJS/catintassist (same? verify - user said C:/catintassist wrong). C:/catintassist/work/repo copy + junction remains; delete before retry to avoid stale copy. MODELS.cmd menu added (Z:/catts/local-coding/MODELS.cmd + copy in catintassist/): 1=Bonsai2 :9103, 2=NeoHorse4B :9107 (new scripts/start_neohorse.ps1), 3=Spark :9105, 4=MiniCPM5 :9104, 5=status, 6=stop-all. :9103 PID 17916 still alive at handoff. Rig Max plan reviewed: Phase1 NeoHorse router OK; Phase3 speculative-decode unverified on Prism fork; Phase4 SnapKV big job, parked.


## Bonsai-2 relaunched + auto-context proxy (2026-09-19 ~13:20): HDD-BOUND, GPU-UNDERFED
Stale :9103 (PID 17916) killed; fresh TQ2_0 server PID 10092 LIVE (8K, q8 KV, ngl 99, logs data/bonsai2-serve*.log). Decode+tool probes PASS direct AND via new proxy PID 4424 on :9106 (scripts/bonsai2_proxy.py, BONSAI2_PROXY.cmd, logs data/bonsai2-proxy*.log; probe script: scripts/bonsai2_probe_live.py). Proxy auto-compresses history >6K tokens via truncate_context + hard-truncate fallback so clients never overflow. Decode measured only ~8-9 tok/s vs 12-13 bench: free RAM 1.89 GB at probe time (was 3.96 at launch) but top hog beyond llama-server 5.02 GB is just browsers - speed gap likely VRAM contention or another GPU user; do NOT recycle mid-session. Next: free-RAM check + auto-context bake-off. NO RAM EATER FOUND in top-8 list.

## Handoff close-out (2026-09-19 evening): taller/smol verified offline, left in working shape
TALLER.cmd fixed (was passing args twice: %* %*). tmp_* scratch deleted. Checks green: hub:check 0 problemas,
npm test 35/35 OK, catts root tests/test_agent_cli.py 9/9 (run with E:/zengatrivi-drive-e/catts/.venv python -
default py3.10 lacks pytest/pydantic). local-coding/ committed. Pendiente: hub LIVE model start/switch cycle
(only apps + adoption exercised so far); free-RAM check + auto-context bake-off; overnight-runner fixes
(max_tokens 2500+, ctx cap 6000, response_format off, delete stale C:/catintassist/work/repo before retry).

## Smol foreign-server gate (2026-09-19 evening): prompt instead of late error
User hit "Otro servidor de modelos esta activo" AFTER configuring model 8 (NeoHorse): the guard only adopted
the Qwen-8123 prior and hard-failed on anything else, and the check ran post-configuration. smol.py now gates
at main() entry via hub-style find_servers (Qwen-8123/residue still excluded): shows model/port/PID and offers
"1. Detenerlo y continuar 2. Salir [1]"; stops via hub.stop_pid, logs to data/smol/stopped-foreign.log.
Stale Bonsai-2 :9103 (PID 10092, from the morning hand-try) stopped by hand; proxy :9106 already gone.
Qwen-8123 (PID 2136) left for the normal pause/restore path. Tests: 39/39.

## supermemory self-host eval (2026-09-19 evening): WORKS, opt-in adoption recommended
User asked quick eval of github.com/supermemoryai/supermemory for local-model use. Hands-on
(plan-approved; binary download authorized by the task). Pinned server-v0.0.8 win64 (291 MB
Bun-compiled, sha256-verified) in local-coding/vendor/supermemory/, wired env-only to
NeoHorse-4B :9107 (llama b10964, stopped after) + local ONNX bge-base-en-v1.5 768d embeddings.
Results: boot 5 s, RAM ~0.73 GB, search 40-80 ms 4/4 correct on distilled atomic facts,
/v4/profile returns dated paste-ready fact list (killer feature), encrypted store persists
across restart (same key/IDs). Ingest is async + LLM-heavy: 5 short docs = ~6.5 min on the 4B
(~1.3 min/doc). Caveats: "lite" binary enforces 10k-doc cap; v0.0.7->0.0.8 had upstream
data-loss migration (pin version, snapshot data/); embeddings weights auto-downloaded from
HF on first use despite "bundled" (pre-seed data/models for offline). Verdict + integration
options (local-work.ps1 --append-system-prompt first) in docs/SUPERMEMORY_EVAL.md. Sandbox +
doc left in place; no existing files changed; Qwen-8123 untouched.

## Memory layer implemented in Taller flow (2026-09-20): DONE, TESTED 43/43
User follow-up: implement supermemory in the way it helps (clarified: no t/s gain, hardware-bound;
gain = effective context, short prompts + retrieved facts, cross-session). Built scripts/memory_ctx.py
(ensure/get/add/stop/status, stdlib, graceful no-op when down; --get works embedding-only with no
model up; --add auto-targets first healthy slot for extraction) + MEMORY.cmd (user start/stop/status,
stop frees ~0.7 GB RAM) + additive block in local-work.ps1 after the consultant-note block: retrieves
project facts capped 3000 chars into --append-system-prompt with "verify against source" header.
Gotcha: without OPENAI_BASE_URL the server omits /health (404) but search/console work — _health
falls back to /. Dedup strips profile [date] prefixes. Unit tests test_memory_ctx.py 4/4, suite
43 passed + 3 subtests. Live-verified: DOWN no-op, ensure boot, get returns seeded facts, status,
CheckOnly intact. Memory left UP (:6767); container localstack has 5 rig facts; MEMORY.cmd stop
reclaims RAM. smol.py/MCP wiring deferred until user asks.

## Memory x3 integrations (2026-09-20 evening): DONE, 51 passed, 1 env-sensitive fail
User approved all three stages, one at a time. Stage 1: bonsai2_proxy inject_memory() prepends
"Persistent local memory" system msg (query = latest user turn, capped to remaining 6K budget,
marker skip, only when memory UP; no auto-start from proxy). Stage 2: local_task ask() prefixes
PLAN/EXECUTE/REVIEW systems via memory_prefix(goal) (saved_answer cache consistent); new
remember_handoff() stores run outcome at complete/pause (best-effort, never fatal) so runs learn
from prior runs. Stage 3: smol.py --memory flag appends memory block to argv system prompt
(default off). Gotcha: local_task must import scripts.memory_ctx (fallback top-level) or memory
silently disables under `python -m scripts.local_task`. Tests: test_bonsai2_proxy 4, test_local_task_memory 3,
SmolMemoryTests 2, live-verified all three paths. Full suite 51 passed + 3 subtests; ONLY
test_turn_without_model_is_502 failed = ENVIRONMENTAL (user-launched llama-server live on :9104
during run; premise "no model" false; left untouched, not a regression — passed earlier today when
slot free). Not yet measured: real with/without-memory Bonsai-2 bake-off (needs user-authorized trial).

## GPU speed-up track started; RX 6600 vanished from system (2026-09-20 night): TOOLS READY, HW ISSUE BLOCKING
User approved plan (Vulkan sweep -> HIP test -> review -> Kaggle shortlist -> PTQ1_0 shader fix -> ROCm doc).
Built scripts/gpu_sweep.py (-b/-ub x KV q8/q4 x runtime matrix over mini/qwen35/bonsai2; own server on
:9151, always stops; gpu_busy abort, RAM floor, timings from /v1/chat/completions; JSON to data/sweeps/)+
test_gpu_sweep.py 14. First sweep run: ALL load_failed, error tail `invalid device: Vulkan1`. Root cause:
**RX 6600 dropped off the machine entirely** — `llama-server --list-devices` (both runtimes) and
Win32_VideoController show ONLY the Vega iGPU ("AMD Radeon(TM) Graphics", Vulkan0, 8 GiB UMA). House
launchers hardcode Vulkan1 -> they would all fail right now; mini server running since ~13:53 is on the
iGPU (slow). Fix attempted in tooling: gpu_sweep auto-detects device via --list-devices (prefers Vulkan1).
HW fix is user-side (reboot / Device Manager rescan / reseat); NOT done autonomously. Second known env
fail re-confirmed: test_turn_without_model_is_502 (model live on :9104; same as previous entry). Built
Kaggle shortlist greenfield: kaggle/bench_kernel.py (script kernel: nvidia-smi check -> Prism Linux CUDA
tarball prism-b10687-5d80cff, cuda-12.8/12.4 + nvidia-wheel fallback -> hf_hub_download candidates ->
same 4 probes as local sweep -> /kaggle/working/results.json; broken candidate never kills the run),
scripts/kaggle_bench.py (check/push/status/pull; kernel-metadata.json gen, candidates inlined over
__CANDIDATES__ marker, weekly quota ledger data/kaggle/quota_ledger.json 30h/wk ISO week, dry-run,
pull to data/kaggle_runs/<slug>/), KAGGLE_BENCH.cmd, kaggle/candidates.json (seed: real PTQ1_0 entry +
user-editable placeholders). pip kaggle installed into E: venv. Tests: test_kaggle_bench.py 14; suite
80 total — 79 pass, only the known env-sensitive chores fail. USER TODO: download kaggle.json
(kaggle.com -> Account -> API) into ~/.kaggle/; bring the RX 6600 back; then rerun sweep + HIP test
(Prism bin-win-hip-radeon) + first Kaggle push.
SUPERSEDED 2026-09-21: the RX 6600 is back (see next entry); sweep/HIP test can run again.

## Cloud-as-build-farm session (2026-09-21): golden-reference track + HIP ladder + AMD v3 runbook; RX 6600 BACK
CORRECTION: the 2026-09-20 "GPU vanished" note is stale - user confirms the RX 6600 is installed and
Win32_VideoController shows "AMD Radeon RX 6600" Status OK driver 32.0.21043.19003. Also: an earlier
explorer report claimed a local HIP runtime at Z:/Models/runtime/llama-prism-b10709-hip - FALSE, no
local HIP build exists (only vulkan/cpu runtimes); the fork's HIP/ROCm assets must be downloaded.
User reframe approved: cloud = build farm for the PTQ1_0 weakest links (ranked: ternary kernels,
no ROCm/HIP build, broken Vulkan path). Built, all tested:
- Golden-reference (CUDA ground truth, free): kaggle/golden_prompts.json (FROZEN spec: 8 prompts,
  greedy temp 0 seed 42, top_logprobs 10, detail 64 tokens; editing it forks the reference),
  kaggle/golden_kernel.py (push --golden; deterministico + logprobs via capability probe +
  test-backend-ops MUL_MAT si viene en el tarball; -> /kaggle/working/golden.json),
  scripts/golden_capture.py (mismo spec contra un server LOCAL vivo -> dump comparable),
  scripts/golden_check.py (compara dumps: primera divergencia char/token, deltas logprob;
  exit 0/1/2). candidates.json: bonsai2-ptq10 marcado golden:true. kaggle_bench.py push --golden
  (slug gold-<stamp>, est 0.9 h, misma cuota); pull resume golden.json.
- HIP ladder sin construir: scripts/hip_prebuilt_test.ps1 (L0 enum GPU, aborta si llama-server
  vivo, baja bin-win-hip-radeon-x64.zip prism-b10687-5d80cff, llama-bench PTQ1_0 con/sin
  HSA_OVERRIDE_GFX_VERSION=10.3.0 -> data/hip_prebuilt/; exit codes 0-5) +
  docs/HIP_PREBUILT_LADDER.md (L0 hecho; L1 win-hip esperable FAIL; L2 ubuntu-rocm-7.2 en
  WSL2 con riesgo driver consumer / USB-boot fallback; L3 = nube).
- AMD cloud v3: docs/AMD_HIP_BUILD_WORKFLOW.md (mision build gfx1032, NO bench; de-risk prebuilt
  rocminfo+test-backend-ops en gfx942 primero; cmake AMDGPU_TARGETS=gfx942;gfx1032; validar;
  empaquetar; hipify = contingencia de dias). v2 Vulkan queda como track alternativo, sin
  paralelizar.
Tests: test_kaggle_bench 17, test_golden_check 7 (24 relacionados OK; suite completa sin nuevas
roturas). PENDING user: kaggle.json en ~/.kaggle/; detener llama-server y correr
hip_prebuilt_test.ps1 (L1); reclamar creditos AMD si L2 falla; luego gold-<stamp> push.

## L1 cerrado + bug URL Kaggle arreglado (2026-09-21, tarde)
- BUG LATENTE arreglado: el tag prism-b10687-5d80cff SOLO tiene zips cudart companion (sin
  tarballs linux) y los assets reales llevan prefijo llama- (ej.
  llama-prism-b10709-9a9394a-bin-linux-cuda-12.8-x64.tar.gz). bench_kernel.py/golden_kernel.py/
  hip_prebuilt_test.ps1/docs apuntaban a URLs 404; todos actualizados a b10709-9a9394a.
  Nunca se detecto porque el push de Kaggle aun no se ejecuta.
- L1 RESULTADO: FAIL (esperado, cerrado). Win-hip prebuilt (307 MB) bajado a
  Z:/Models/runtime/llama-prism-hip-win; llama-server --list-devices -> (none) con y sin
  HSA_OVERRIDE_GFX_VERSION=10.3.0; ggml-hip.dll no carga (LoadLibrary err=126; amdhip64.dll
  del sistema v10.0.3584.0 demasiado viejo). Aunque se instalara HIP SDK actual, gfx1032 no
  esta en la matriz Windows. T3 queda respondido; NO instalar el SDK.
- Estado de gates: llama-server vivo (PID 21704, no tocado), kaggle.json sigue FALTA, WSL2 sin
  distros (`wsl -l -v` vacio) -> L2 requiere wsl --install -d Ubuntu (o USB-boot) + asset
  llama-prism-b10709-9a9394a-bin-ubuntu-rocm-7.2-x64.tar.gz.

## Golden CUDA conseguida + toolchain local Vulkan LISTA + baseline reproducido (2026-09-22 madrugada)
- Kaggle: token KGAT -> ~/.kaggle/access_token (kaggle_bench kaggle_conf soporta token-file,
  username via config view cacheado). v1 kernel ERROR (json.dumps mete true/false en python:
  arreglado con repr()); v2 COMPLETE. Golden CUDA en data/kaggle_runs/gold-20260921/golden.json
  (spec 25005c6c2ea1d69c, 8 prompts 501 tokens top-logprobs, server b10709 CUDA T4; PTQ1_0
  11.9-17 t/s en T4; backend_ops ausente en tarball). Cuota 1.8/30h.
- Toolchain local (user aprobo "use our resources"): C:/tools ~4.5GB portatil (llvm-mingw,
  cmake/ninja via pip venv, glslang 16.6 renombrado a glslangValidator.exe, Vulkan/SPIRV
  headers, libvulkan-1.a via dlltool) + SHIM glslc.exe (C compila a glslangValidator: flags,
  #include expansion, silencio stdout/stderr, errores de extension traducidos) porque el build
  exige glslc (shaderc solo en SDK 1GB). Ver docs/LOCAL_VULKAN_BUILD.md (todo el how-to).
- Build fork @prism-b10709-9a9394a EXITOSO tras 4 parches minimos (cstdlib x3, setenv/unsetenv
  shim) y flags _WIN32_WINNT=0x0A00. llama-server 76MB, llama-bench 70MB, test-backend-ops 62MB.
  C: QUEMO 99%: solo targets nombrados, nunca ninja pelado (rellena con ~50 tests).
- BASELINE REPRODUCIDO EXACTO (server bonsai2 coexistiendo): MUL_MAT n=1 m=4096 k=14336:
  ptq1_0 601.17us/195.35 GFLOPS (doc decia 602/195), tq2_0 94.60us/1.24 TFLOPS, q4_0 94.32us.
  Correctness 39/39 OK. Fix LUT de ptq1_0.glsl ahora es 100% local: edit -> ninja
  test-backend-ops -> perf; validacion final = golden_check vs golden CUDA.
- Proximo: escribir el shader LUT (objetivo 602 -> ~100us => decode 3.3 -> 20-24 t/s), luego
  golden_check + A/B calidad. L2/AMD cloud solo si Vulkan fix falla.

## PTQ1_0 matvec especializado: CORRECTO, 601->441us (195->266 GFLOPS), decode 3.3->4.5 t/s (2026-09-22)
- Nuevo shader ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp (modelo tq2_0: 16 threads/bloque,
  thread = 8 elementos contiguos, trit index uniforme por thread, cadena base-3 desenrollada).
  Registrado: gen tool mapping +type "ptq1_0" (ya estaba en type_names, NO duplicar) y pipelines
  matvec SIEMPRE con params stdq ({2*rm_stdq}, use_subgroups, [reduc]); los subgroup16/rm_kq de
  tq2_0 DAN RESULTADOS INCORRECTOS aqui (falla + lento global).
- Bugs encontrados y arreglados: y_idx olvidaba i*QUANT_K (todos los bloques leian las mismas
  128 activaciones); vectorizacion ivec4 del trit-decode fue MAS LENTA (502us, revertida) ->
  el limite es ANCHO DE BANDA (33 GB/s logrados vs 132 de tq2_0), no la aritmetica. Siguiente
  palanca: loads u32/packed16 del bloque + tuning workgroup.
- VERIFICACION: test-backend-ops MUL_MAT ptq1_0 3/3 OK; llama-bench PTQ1_0 RX 6600 (GPU
  exclusiva): tg32 4.50 ± 0.02 t/s (antes 3.3), pp128 59.5 t/s. TQ2_0 sigue ganando 12-13.
- Toolchain notes: llama-bench de este build necesita PATH con llvm-mingw/bin (libc++/libomp
  dinamicos); el exe linkado durante el disco lleno quedo corrupto (rc 127 silencioso, relink
  curo); -c no es flag de llama-bench en el fork; GPU via GGML_VK_VISIBLE_DEVICES=1.
- Parches nuevos acumulados en C:/src (ademas de los 4 anteriores): CMakeLists ggml-vulkan
  -O1 para TUs generados (clang LLVM OOM con 16GB + server residente).
- bonsai2 :9103 DETENIDO para el bench (user: relanzar con MODELS.cmd 1). Golden CUDA sigue
  pendiente de usar para validacion end-to-end del kernel nuevo (golden_capture vs Kaggle).

## Veredicto Kaggle-shader + sweep: -O y loads descartados; queda config pipeline (2026-09-22 mediodia)
- W1 Kaggle-compile WORKS: kernel CPU (sin cuota GPU) shader-20260922 compila las variantes con
  glslang+spirv-opt -O (== glslc -O); 8 spv + manifest. Import via shim bypass: clave
  mul_mat_vec_ptq1_0.<fnv1a64 sobre fuente expandida sin \r>.<f32|f16>[_sub].spv en
  C:/tools/bin/spv-precompiled/ (shim las sirve byte-a-byte, verificado cmp).
- W2 VEREDICTO: spv OPTIMO = 441.19us/266.19 GFLOPS == unoptimized (441.56/265.96), 3/3 OK.
  -O NO era el cuello. Hipotesis del user testeada y cerrada.
- W3 sweep local (scripts/shader_sweep.py, JSON en data/shader_sweep/): v0_scalar 438.68us/267.7
  GANA; v1_packed16 (u32 loads + unpack8 + chain vec) 460.52us/255.0 = PEOR. Tipos: packed16
  struct ptq1_0 aniadido a types.glsl (compila bien). Aritmetica y ancho de loads descartados.
- CONCLUSION tecnicas: kernel bound por config pipeline/reduccion, no por shader-micro. tq2_0
  corre con wg=subgroup_size16 + reduccion SUBGROUP ([reduc16], force16) + wg_denoms {rm_kq};
  ptq1_0 usa wg=subgroup(32) + SHMEM reduction. Intento copiar config tq2_0 tal cual FALLO
  correctitud (sospecha: spec constants {wg,rm_kq,i+1} fijan NUM_ROWS/it_size y la combinacion
  requiere ajustar el shader o el driver no soporta force16 en este pipeline). NEXT SESSION:
  leer create_pipeline spec-constant layout + probar config subgroup16 CON el shader ajustado
  (it_size=1) paso a paso. Alternativa: PR upstream del kernel actual (1.36x) + issue pidiendo
  la config.
- Nota meta: pipeline Kaggle->local de shaders reutilizable (shader_variants/ + push --shader +
  bypass) para cualquier experimento futuro de shaders sin instalar SDK.

## MATVEC ROUND 3 — PTQ1_0 threads-extra + vecq REAL layout (2026-09-25): TECHO CONFIRMADO, TRACK CERRADO
- Optimización #3 implementada: vecq PTQ1_0 con repack4 vectorizado (sin LUT, aritmética closed-form) para layout REAL → **5491 µs lm_head** (PEOR que f16 LUT 5112 µs). Confirma night-9: vecq no gana en PTQ1_0.
- Threads-extra walk (WG=256, 32 hilos/bloque-worth, 4 elems/hilo contiguos) en f16 LUT → **5044 µs lm_head** (-1.3% vs baseline), gate/up -14% (328 µs). 68/68 suite OK.
- TQ2_0 vecq 1643 µs (200 GB/s), Q4_0 3332 µs (217 GB/s) — sin regresión.
- **3 diseños consecutivos sin mover lm_head <3000 µs**: paired-row R2 (4799), vecq R3a (5491), threads-extra R3b (5044). Techo físico del layout PTQ1_0 = ~55 GB/s (5000-5100 µs).
- **Cierre del track PTQ1_0**: layout GGUF impide coalescing de pesos (28 B/128 elems = 0.22 B/elem vs 0.5 TQ2_0 vs 1.0 q4_0). Único camino real = optimización #2 (repack GGUF element-major CONTIGUO) — sesión dedicada + golden gate.
- Recomendación: **TQ2_0 como daily driver** (12-13 t/s, vecq funcional); perseguir requant TQ2_0 (Colab runbook). Docs: MATVEC_PROFILE_ROUND3_2026-09-25.md + SESSION_CONTEXT.md.

## LUT WINS al nivel kernel + DIAGNOSTICO DECISIVO del camino de decode (2026-09-22 tarde)
- T1: spec constants = ID0 BLOCK_SIZE(=wg.x), ID1 NUM_ROWS, ID2 NUM_COLS. subgroup_size16 =
  max(subgroup,16) = 32 en RX 6600 (tq2_0 NO corre 16-wide aqui). Enum reduccion: SHMEM0/HYBRID1/SUBGROUP2.
- T2: env GGML_PTQ1_0_MATVEC (stdq|sub16|sub16hyb) en las 2 lineas de pipeline matvec ptq1_0
  (sin rebuild por iteracion). sub16hyb FALLO en createComputePipeline (ErrorUnknown) en este driver.
- v2_lut.comp (shader_variants/): LUT shared 5x256 (trit j del byte b), fill una vez por
  workgroup + barrier; lookup = ~4 ops/elemento vs ~14 de la cadena. RESULTADO: matvec
  441 -> 247-250us (470-475 GFLOPS), 3/3 OK con stdq y sub16. 2.4x sobre el 601 original.
- PERO llama-bench tg32 SIGUE 4.5 t/s con el kernel nuevo (y 4.67 con pipeline ROTO sub16hyb)
  => EL DECODE DEL MODELO NO USA pipeline_dequant_mul_mat_vec_*_f32/f16: usa la tercera
  familia, pipeline_dequant_mul_mat_vec_q8_1 (mul_mat_vecq.comp, B cuantizada a q8_1).
  El acelerador de decode real = rama ptq1_0 de mul_mat_vecq.comp / mul_mat_vecq_funcs.glsl
  => aplicar la MISMA tecnica LUT ahi (next session; el truco del pipeline roto diagnostica
  que camino corre). Nota: los 4.5 t/s ya logrados probablemente vienen del header ptq1_0.glsl
  desenrollado que SI consume vecq.
- Canonical actual en C:/src = v2_lut (sub16 por env). bonsai2 relanzado.

## RESULTADO FINAL sesion shader: PTQ1_0 3.3 -> 6.4 t/s; LUT verificado vs golden CUDA (2026-09-22 tarde-2)
- Dispatcher understood: quantize_y (MMVQ via q8_1) activo por integer_dot_product en RX 6600
  (ggml-vulkan.cpp:9640). A/B switch GGML_PTQ1_0_NO_MMVQ=1 (edit guardado en el arbol local).
- llama-bench REBUILDADO con todo el shader set actual: tg32 6.35 (MMVQ) vs 6.43 (NO_MMVQ =
  LUT matvec) — EMPATE; el 4.5 anterior era un llama-bench con shaders viejos embebidos
  (leccion: EMBEDED shaders — relink llama-bench tras cada cambio de shader).
- TOTAL sesion: decode 3.3 -> 6.35-6.43 t/s (+92%); matvec op 601 -> 247us (2.4x, 3/3).
- GOLDEN VERIFICACION end-to-end (NO_MMVQ, LUT path): 7/8 prompts IDENTICOS char-a-char al
  golden CUDA T4 (spec 25005c6c match; lp_d max 0.05); toolcall diverge en token 0 por
  top-2 a 0.007 nats en CUDA (coin-flip numerico, no bug). Dump:
  data/golden/bonsai2-ptq10-lut-vulkan-20260922-131535.json (+lut-renamed.json).
- Posicion: TQ2_0 sigue 12-13 t/s pero PTQ1_0 ahora 6.4 con ~1 GB menos VRAM (ctx 16K+ viable).
- SIGUIENTE (semana proxima, budget aparte): LUT en la rama ptq1_0 de mul_mat_vecq (MMVQ):
  ahi vive el 2x restante (35 vs 80 GB/s efectivos). Upstream PR material listo: kernel v2_lut
  + env A/B + golden methodology + numeros.
- GOTCHA golden_check: compara por model name (usar --name bonsai2-ptq10 en captures futuros).

## CIERRE shader-dev (2026-09-22 noche): cut-off alcanzado, PTQ1_0 decode ~6.4-6.7 t/s es el techo del rig
- Vecq port COMPLETADO y CORRECTO: ptq1_0 anadido a mul_mat_vecq (K_PER_ITER=16, repack4
  region-uniform con LUT shared 5x256 + offset +8, correccion 4*dsb.y heredada de Q2_0;
  parches: comp K_PER_ITER+shmem+fill, funcs get_dm/repack4/mmvq_dot_product, gen tool x2
  listas (string_to_spv q8_1 + arr_dmmv decl), vulkan.cpp pipeline create).
- A/B FINAL (GPU exclusivo, misma sesion): vecq 6.32-6.67, NO_MMVQ LUT-matvec 6.40-6.43,
  matvec 16x8 LUT 247-250us, matvec 8x16 u32-loads 265us, closed-form ptq1_0.glsl igual.
  CINCO disenos de matmul independientes => 6.3-6.7 SIEMPRE. El cuello de decode NO es el
  decode de trits ni el matmul: el techo esta fuera (sched/attention/otras ops por-token).
  pp128 llego a 77 con GPU exclusivo (vs 59 con server coexistiendo; revisar comparaciones
  antiguas: muchas corrian con bonsai2 vivo).
- Config final del arbol: v2_lut matvec (247us, el mejor medido) + closed-form accessor +
  vecq port + env switches GGML_PTQ1_0_MATVEC / GGML_PTQ1_0_NO_MMVQ. 3/3 correcto todo.
- Veredicto budget:shader work CERRADO. PTQ1_0: 3.3 -> ~6.4-6.7 t/s (+95%), 1 GB menos VRAM
  que TQ2_0 (que sigue 12.2 en el mismo binario). Material upstream PR listo (kernel+vecq+
  env+metodologia golden+numeros); siguiente palanca real seria fuera del shader (HIP path,
  o investigar el bottleneck no-matmul con perfilador si algun dia importa).
- bonsai2 :9103 relanzado al cerrar.

STANDING RULE (user, 2026-09-22): C: esta CRONICAMENTE lleno (99%, era 96% antes de todo esto)
- ser mindful: nada nuevo grande en C:; descargas/caches/modelos -> Z:; solo `ninja` con
  targets nombrados en C:/src (nunca pelado); borrar zips instaladores tras extraer; vigilar
  >=1.5-2GB libres. Footprint actual del build en C: ~1.6GB (tools 860MB + src/build 780MB
  tras limpiar tests/exes/.git/temp); el loop de shader solo reemplaza ~62MB por relink.

## Golden-check de TQ2_0 (NO pasa el bar) + preset largo 32K adoptado (2026-09-22 noche-2)
- TAREA 1 del assessment (golden-check del daily driver): capture contra :9103 vivo
  (TQ2_0, runtime shipped llama-prism-b10685-vulkan, 8K q8 KV, reasoning-effort medium,
  GPU exclusiva) -> `data/golden/bonsai2-tq2_0-goldencheck-20260922.json`, spec
  25005c6c2ea1d69c match, 8 prompts con top-logprobs. Sin editar golden_prompts.json.
- RESULTADO vs golden CUDA T4 (PTQ1_0): 4/8 DIVERGENTES => el bar (<=1/8) NO se cumple.
  OK: count300 (320 tok), tocents, arith, elements. DIVERGEN: code_summary (token 18),
  toolcall (token 1), es_mar (token 6), fox_cont (token 1).
- En los 4 casos TQ2_0 elige el token rank-2/3 del golden; gap top1-top2 del golden en ese
  paso: 0.13 / 0.45 / 1.34 / 0.62 nats. NO son coin-flips tipo PTQ1_0 (0.007 nats):
  es_mar tenia 1.34 nats de separacion => desvio numerico real de la doble cuantizacion.
- PERO el contenido sobrevive: los 4 textos siguen gramaticales y correctos en sustancia
  (es_mar: 'bajo la luz del sol' vs 'bajo el sol del mediodia'; code_summary solo pierde
  'argument'; fox_cont cambia la continuacion pero es coherente; toolcall pasa de refusal
  seco a refusal con oferta de ayuda). Lectura: fidelity gap medible, NO corrupcion visible.
- Control misma sesion: PTQ1_0 local (LUT b10709) = 7/8 identico => el backend Vulkan solo
  aporta ~1/8; los 3 extra son de TQ2_0. Caveat de evidencia: no esta aislado TQ2_0-vs-runtime
  (TQ2_0 corrio en b10685, PTQ1_0 en el fork b10709). Control limpio pendiente = capturar
  PTQ1_0 en el MISMO b10685. Muestra: 8 prompts, 1 corrida.
- TAREA 2 adopted: PRESETS['bonsai2']['high'] pasa de `{-c 32768}` (la vieja etiqueta decia
  ~3 tok/s) a `{-c 32768 -ctk q4_0 -ctv q4_0}` = 10.9 tok/s con 16K de documento (T2 9/21).
  Nota de STANDALONE['bonsai2'] y comentario de start_bonsai2.ps1 actualizados; el default
  sigue -c 8192. Uso: `CATTS.cmd start bonsai2 --preset high` (hub: presets=mid,low,high).
- Verificacion: standalone_args('bonsai2','high') devuelve -c 32768 -ctk q4_0 -ctv q4_0 con
  device resuelto; tests del proyecto (hub/smol) sin roturas.
- Siguiente (del assessment, sin empezar): profilear el piso no-matmul con el build de
  C:/src (task 3), PR upstream (task 4), gpu_sweep real (task 5), HIP L2 (task 6).

## CPU decision gate del drift de TQ2_0: ES LA CUANTIZACION, no el kernel (2026-09-22 noche-2)
- Gate corrido tal cual: runtime shipped b10685, `-ngl 0` (CPU), flags identicos al capture
  GPU, :9103 y la GPU sin tocar. Dump data/tmp/tq2-cpu-20260922.json (spec 25005c6c match,
  8/8 prompts, top-logprobs).
- golden_check vs golden CUDA: 4/8 DIVERGENTES (exit 1) = code_summary(t18), toolcall(t1),
  es_mar(t6), fox_cont(t1). MISMOS prompts, MISMOS pasos y MISMOS tokens de reemplazo que la
  corrida Vulkan ('.' / ' can' / ' la' / ' scene').
- CPU vs Vulkan: byte-identicos en 7/8 prompts; fox_cont coincide hasta el token 7 y ahi se
  abre. Dos implementaciones de kernel independientes coinciden entre si y discrepan del
  golden PTQ1_0 CUDA => el drift esta en los PESOS TQ2_0 (doble cuantizacion), no en el
  shader tq2_0. Queda descartada la hipotesis kernel-level.
- Costo del run: 0.54-0.74 t/s decode, ~1.15 t/s prompt eval, count300 (320 tok) 462 s,
  capture completa ~16 min + ~2 min de carga. RAM: 6.48 GB residentes, libre bajo a ~0.7 GB
  (la iGPU UMA se come ~5 GB de 15.4). Lento pero estable, sin thrash-kill. Servidor CPU
  apagado al terminar; libre volvio a 7.7 GB.
- VEREDICTO: Path B (requant desde F16, idealmente +imatrix) ES el fix correcto y esta
  justificado; no gastar esfuerzo de shader en tq2_0 por fidelidad. Constraint real del
  requant = disco del host (~61 GB), no RAM. Costo del gate: ~30 min de reloj, cero cuota.
- Artefactos: data/tmp/tq2-cpu-20260922.json, data/golden/bonsai2-tq2_0-goldencheck-20260922.json,
  log del server CPU data/tmp/tq2-cpu-server.err.log.

## Evals del autor de Bonsai-2: extra-high effort + 131k thinking (2026-09-22, capturado 09-23)
- Fuente: thread de Barron (@barronnotbaron, 22 sep 2026) + repo barronprism/Bonsai2-Demos.
  Captura completa y analisis en docs/BONSAI2_AUTHOR_EVAL_THREAD_2026-09-22.md.
- Datos del autor: "5.9 GB of weights for a 27B model" (= nuestro PTQ1_0, 5.95 GB; el quant de
  referencia es PTQ1_0, NO TQ2_0). IMO 2026 post-cutoff vs Qwen3.8 27B FP (54 GB) y Gemma 4 12B
  QAT: ambos en bronce humano alto (16-22); Bonsai retuvo 95% del score de Qwen-FP, ~70% del
  tiempo, pero ~22% MAS thinking tokens. Config: llama.cpp default, sin internet, sin tools,
  extra-high reasoning, 131k de contexto de pensamiento y luego respuesta forzada.
- Implicaciones: (1) los numeros publicados se midieron en extra-high -> bajar effort con
  --reasoning-effort/--reasoning-budget es un trade y debe puntuarse contra el golden (top-10
  logprobs), no solo contra wall time; (2) nuestro 0/6 a max_tokens 1200 es config, no limite
  del modelo: tareas duras necesitan max_tokens >= 16k; (3) el "70% del tiempo" es relativo al
  hardware del autor (no extrapolar a los ~34-37 t/s de techo del RX 6600); (4) no podemos correr
  el baseline FP27B local (54 GB): toda comparacion local se ancla al golden CUDA o a lo publicado.
- Sin cambios de runtime ni flags por ahora; el addendum de BONSAI2_REASONING_EFFORT.md apunta
  el criterio PASS de T1 al golden.


## Overflows de contexto: confirmados en logs + guard aplicado (2026-09-23)
- User reportaba que "los modelos explotan" al recibir prompts mas largos que su contexto; la
  creencia previa ("eso no es problema") es FALSA. Evidencia on-rig: data/hub/logs/spark.log
  lineas 17-42 `E srv send_error: request (19947 tokens) exceeds the available context size
  (16384 tokens)` y 454/547 `(70076/70591 tokens) exceeds ... (65536)`. Reproducido a 16K y 64K.
- Causa: el context shift de llama.cpp solo descarta tokens YA cacheados de requests previos; un
  prompt renderizado mayor que `-c` no se puede acomodar -> error de servidor. `--no-context-shift`
  (slot Smol) no lo causa, solo lo hace mas ruidoso. El proxy :9106 protegia SOLO a quien le
  apuntaba; Spark :9105, Qwen3.5 :9102, Qwen3.8 :9101, MiniCPM5 :9104 y el :9103 directo no tenian
  guard: tomaban lo que el cliente mandara.
- Segundo modo, silencioso: `bonsai2_proxy._hard_truncate` recortaba "lo ultimo que quepa" y podia
  TIRAR el ultimo turno de usuario si ese mensaje solo ya pasaba el budget (un archivo pegado) ->
  el modelo respondia a una pregunta que nunca vio (el sintoma de "explota"), sin ninguna linea de
  error. Fix: `_hard_truncate` ahora FIJA el ultimo turno de usuario y, si no cabe, lo recorta en
  sitio (cabeza+cola + "[...middle dropped by proxy...]"), preservando system y turnos recientes.
- Nuevo launcher generico CTX_PROXY.cmd <upstream_port> <listen_port> <ctx> [budget] [model]
  (mismo codigo del proxy, cualquier puerto): ej. `CTX_PROXY.cmd 9105 9109 16384 12000 spark25`.
- Tests: tests/test_bonsai2_proxy.py 8 passed (3 nuevos: turno sobredimensionado recortado, system
  preservado, historial que termina en assistant sigue llevando la instruccion).
- Tabla de decision modelo/puerto/t/s/contexto guardada en docs/MODEL_PICK_AND_CONTEXT_OVERFLOW_2026-09-23.md
  (tamanos verificados en disco; ojo: el "~15 GB" del roster para qwen27 es 7.91 GB real, parece stale).
- Pendiente opcional: apuntar los clientes (Zed/agentes) a puertos de proxy en vez de directo a
  :9103/:9105/:9102; y revisar que el path de resumen del proxy colapsa todo el historial a UN
  mensaje de usuario (rompe roles system/tool en uso agentico).


## Recon: "Bonsai-2-27B-1bit-CRACK-GGUF" = el MISMO archivo que ya tenemos (2026-09-23)
- User paso un link a huggingface.co/dealignai/Bonsai-2-27B-1bit-CRACK-GGUF ("creo que es lo mismo,
  por si acaso"). Verificado: NO es Ming-Image (eso es otra familia, ver abajo) y NO es un quant
  nuevo. Un solo GGUF `Bonsai-2-27B-PTQ1_0-CRACK.gguf` con totalFileSize 5946648928 bytes, que es
  EXACTAMENTE el tamano de nuestro canonical data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf
  (prism-ml/Ternary-Bonsai-2-27B-gguf rev 6ed5e12b, sha256 53107f53...). Re-etiquetado, no requant.
  Conclusion: no descargar nada; ya corremos ese archivo (6.4-6.7 t/s). Doc:
  docs/BONSAI2_CRACK_GGUF_RECON_2026-09-23.md. Higiene: procedencia no verificada, el nombre implica
  bypass de licencia; regla vigente = solo download_verified_model.py con SHA256 + .verified.json.
- Hallazgo util: la plantilla Jinja embebida en ese repo confirma de forma independiente el default
  `reasoning_effort='xhigh'` y que SOLO acepta xhigh|medium|low (raise_exception si no). No existe
  "high": el A/B de T1 debe usar esos tres strings o --reasoning-budget N. Anotado en el addendum
  de BONSAI2_REASONING_EFFORT.md.
- Ming-Image-0.1-Design/Layer (announcement con ModelScope, 6B, MIT, #1 UI/UX de AA, 4.3x vs baseline
  20B, 2048x2048, RGBA): claims de marketing, veredicto del 09-22 SIN cambios (no hay GGUF, ~52.9 GB,
  torch custom, target 80 GiB CUDA -> no corre en este rig). Addendum agregado a
  docs/MING_IMAGE_0.1_DESIGN_EVAL_2026-09-22.md; el unico dato nuevo util es la licencia MIT.


## MiniCPM5 a contexto completo via `catts local` + OMP alineado (2026-09-23 tarde): ARREGLADO
Sintoma del user: levanto MiniCPM5 con `catts local`; no usaba ~100K y una sesion OMP NUEVA
moria con "context compression" al primer "hi". Causa (dos capas): (a) DEFAULT_PRESET['mini']
era 'mid' = 32K con KV q8, y el preset 'long' solo cambiaba -c (dejaba KV q8, que faulta el
driver Vulkan a ~84K tokens; 2026-09-20); (b) el modelo OMP declaraba contextWindow 32768 y con
compaction.thresholdPercent 65 el umbral cae en ~21.3K = justo el baseline del agente
(~18-21K de system prompt + esquemas), asi que compactaba en el primer turno.
Arreglo (en Z:/catts/local-coding): PRESETS['mini'] pone 'long' primero y con KV q4_0
('-c 131072 -ctk q4_0 -ctv q4_0'); DEFAULT_PRESET['mini']='long'; smol_server_args fuerza
KV q4_0 para mini cuando el -c efectivo es >=65536, sin importar como se pida. El perfil por
modelo (data/smol/profiles/mini) lo regenera smol.py: queda en contextWindow 131072.
OMP global (C:/Users/<user>/.omp/agent): restaurado config.yml VALIDO (omp habia cuarentenado
el anterior a las 14:11 por YAML roto: 'default' anidado bajo 'smol'; se conservo la intencion,
default: spark/spark25); provider minicpm5 con contextWindow 131072, reasoning:true y compat
reasoning_content (thinking ON); provider smol.mini tambien 131072.
Verificado: hub.py check 0 problemas (smol:mini presets=long,mid), unittest 103/103 OK, argv
impreso con -c 131072 -ctk q4_0 -ctv q4_0 (sin arrancar modelo). NO se probo un arranque REAL
a 131K: la GPU la tenia Spark :9105 (PID 55252) y otro agente trabajaba spark+omp en paralelo.
Pendiente: un launch real de mini a 131K cuando la GPU este libre.

## GPU crawl light-mode: leads de finds.txt verificados (2026-09-24)
User pidio retomar "the gpu crawl" (su agente anterior se perdio; no habia automation/workflow
activo — output sobreviviente: Z:/catts/finds.txt). Sesion SOLO web (user usando el PC, sin GPU
exclusiva). Informe completo: docs/GPU_CRAWL_2026-09-24.md.
- Lead 1 GSQ-RCO IQ2_XS-mtp (ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF): REAL y es GGUF ESTANDAR
  (IQ2/IQ3 types; el comment "solo NVIDIA" NO esta en la model card). MTP head embebida
  (PR llama.cpp #22673, +33-39% en CUDA, draft 2-3); Vulkan probable pero sin prueba RDNA2.
  PERO 8.75 GB > 8 GB VRAM -> offload parcial ~1-1.5 GB: ~8-9 t/s sin MTP, ~11-12 con MTP
  SI acepta bien = a lo sumo EMPATA con TQ2_0 (12.2-13). Decision de download+trial = del user.
- Lead 2 ROCmFPX (ciru-ai): CERRADO para gfx1032 — validado solo en gfx1151/Strix, sin
  prebuilts Windows en el README (claim de finds.txt "builds Windows con ROCm 7" SIN verificar),
  FP2/4/6/7 sin Vulkan, y no corre nuestros ternary de todos modos. STRIX_LEAN de pugant: no es
  para este rig.
- Lead 3 Bonsai 27B Q1_0 3.8GB: STALE — ya esta en el rig y ya tiene veredicto (16.7 t/s,
  7/12 checkout FAIL 2026-09-07). DSpark drafter en el GGUF de Mobius = nota, no accion.
- Lead 4 Escha W2: real pero necesita fork custom (Ajay9o9/llama.cpp-escha); watch.
- Pesado (profile harness day-1, gpu_sweep real, HIP L2) sigue PARKED hasta que la GPU quede
  libre. Sin downloads, sin launches, C: intacto.

## D1 per-op profile: el 2x faltante esta DENTRO del matvec (2026-09-24, GPU libre)
User libero la GPU -> corrio el profile-first plan. (1) Baseline d1 3-run (profile_day1.ps1
PRIMERA corrida real): 3/3 OK, mean 9.36 t/s PERO con ~2.5 GB RAM libre (user en el PC) =
firma low-RAM conocida (-25-30% vs roster 12-13); loads 127-150 s (HDD bajo contention).
Re-correr limpio con >=4 GB. JSON data/profile/d1_20260924-150704.json.
- (2) Per-op capture NUEVO script scripts/d1_perop_profile.py: usa GGML_VK_PERF_LOGGER del
  fork (timestamp queries YA integradas - no hizo falta instrumentar nada ni rebuild). Gotcha
  arreglado: el exe de C:/src necesita C:\tools\llvm-mingw\bin en PATH (0xC0000139 si no).
  Parsea la ULTIMA tabla "Vulkan Timings:" = decode steady-state.
- RESULTADO (TQ2_0 q4 KV / PTQ1_0 q8 KV, 8K, C:/src): TQ2_0 GPU-sum 81.8 ms/tok (->12.2 t/s
  = roster exacto), PTQ1_0 157.8 ms/tok (->6.3 t/s). MUL_MAT 83.7%/92.4% del tiempo; TODO lo
  no-matmul 8-16% (12-13 ms); FLASH_ATTN 1-4% -> la hipotesis "el cuello esta fuera del
  matmul" QUEDA REFUTADA. Wall ≈ GPU-sum con RAM sana (ambos modelos).
- Causa del 2x PTQ1_0: instancias matvec a 36-38 GB/s vs 110 GB/s de TQ2_0 en MISMAS shapes
  (ratio 2.0-2.4x con solo 1.24x mas bytes). El microbench viejo (m=4096 k=14336, 59 GB/s)
  NOS ENGAÑO: las shapes de produccion (m=17408 k=5120 x128, m=5120 k=17408 x64, m=10240
  k=5120 x48, lm_head 248320 x1) corren mucho mas lento por instancia.
- NEXT (D2): test-backend-ops MUL_MAT en las shapes de PRODUCCION (no la vieja), levar
  ptq1_0 36->110 GB/s => ~11.5 t/s fiel; TQ2_0 95->130-160 => 20-24 t/s. golden_check tras
  cada cambio. JSONs: data/profile/d1_perop_20260924-{151504,152010}.json. Detalle completo:
  docs/GPU_SPEEDUP_ASSESSMENT_2026-09-22.md seccion "D1 profile RESULT".
- BONUS crawl: AMBOS runtimes instalados (llama-vulkan-b10964 Y prism b10685) tienen
  --spec-type draft-mtp y draft-dspark -> el trial GSQ-RCO IQ2_XS-mtp y el drafter DSpark
  NO requieren runtime nuevo (ver docs/GPU_CRAWL_2026-09-24.md).

## Night runner: trabajo nocturno SIN modelo (2026-09-24 tarde)
Diagnosis del user: de dia el esta en el PC (GPU ocupada, solo trabajo ligero); de noche los
agentes con modelo "commit errors / miss things / observaciones sin accion" y no se logra nada.
Fix estructural: la noche = SOLO scripts con preflight (cero modelos, cero tokens, cero git);
el juicio queda para la sesion de dia. Hoy lo valido el propio dia: crawl + per-op profile
salieron con user en el PC (no necesitaban GPU).
- scripts/night_jobs.ps1: runner nocturno. Reglas duras: nunca mata procesos (skip),
  nunca toca git, 1 corrida por dia (lock data/night/<fecha>/lock.flag), trabajo GPU solo si
  no hay llama-server y 9103/9151 libres; baseline exige >=4096 MB RAM libre (el numero
  LIMPIO); sweep se cancela solo si ya son las 06:30. Al final escribe
  data/night/<fecha>/MORNING_REPORT.md (PASS/FAIL/SKIP + numeros + paths) y el runner.log.
  Jobs noche-1: baseline profile_day1 x3 + gpu_sweep.py matriz default completa (la primera
  vez que produzca datos).
- TAREA PROGRAMADA: "CATTS-NightJobs" (schtasks, DAILY 02:30, next run 25/09/2026 02:30).
  Cancelar: `schtasks /Delete /TN CATTS-NightJobs`. Correr a mano: powershell -File
  Z:/catts/local-coding/scripts/night_jobs.ps1 (o -PreflightOnly). Smoke test preflight OK.
- Flujo dia->noche->dia: la sesion de dia lee MORNING_REPORT primero, decide/builda (build =
  CPU, cabe de dia), y empuja validaciones (bench/golden/sweep) a la noche siguiente.
  Si un job falla, el reporte lo dice con reason - nada se reintenta ni corrige solo.

## D2 prep sin tokens: IC-confound hallado + shapes de produccion en la suite (2026-09-24 tarde-2)
User pregunto por que hace falta medir t/s corriendo tokens. Respuesta con datos: para
DIAGNOSTICAR no hace falta (todo esto corrio sin modelo, solo un kernel por vez en
test-backend-ops); para CONFIRMAR end-to-end si (2 precedentes de benches que mintieron).
- Parche en C:/src/llama.cpp/tests/test-backend-ops.cpp: 7 shapes de produccion registradas
  para q4_0/PTQ1_0/TQ2_0 (n=1) tras el loop 4096x14336; ninja target nombrado (~2 min).
- DESCUBRIMIENTO (higiene de medicion): la suite relee el mismo tensor -> si pesa <=32 MB se
  queda en la Infinity Cache de la 6600 y MIENTE: tq2_0 161 GB/s en-suite vs 102 GB/s frio
  (produccion); ptq1_0 52 -> 41. La shape lm_head (280 MB, inmune a IC) matchea produccion
  casi exacta (6698 vs 6686 us) -> usar ESA para A/Bs de kernels. Todos los numeros de
  test-backend-ops pre-2026-09-24 (incl. el 94.6 us / "1.24 TFLOPS" de tq2_0) estan inflados.
- El kernel ptq1_0 es 2.3-2.9x peor por byte que tq2_0 en TODAS las shapes (frio: 41 vs
  102 GB/s = 18% vs 46% del pico). tq2_0 usa repack4 + integer dot (la 6600 lo tiene);
  ptq1_0 decodifica base-3 (LUT) + FMA f32. La shape nunca fue el problema.
- PROTOCOLO D2 (sin tokens): editar shader -> ninja test-backend-ops -> perf en lm_head
  (frio-verdad) + test de correctitud -> repetir; un decode corto solo para confirmar.
  Meta: ptq1_0 a paridad tq2_0 => ~14 t/s fiel. Tabla completa en
  GPU_SPEEDUP_ASSESSMENT_2026-09-22.md, seccion "D2 prep".
- Nota toolchain: ninja vive en E:/zengatrivi-drive-e/catts/.venv/Scripts (agregar a PATH
  junto a C:/tools/llvm-mingw/bin).

## D2 ronda 1: vecq NUNCA compilo (bug de 09-22) - reparado; tercer empate de disenos (2026-09-24 noche)
Iteracion token-free del kernel ptq1_0. En orden:
- HALLAZGO GRANDE: mul_mat_vecq_funcs.glsl estaba ROTO desde la sesion 09-22 (paste doble al
  final: IQ1_S/IQ1_M duplicados byte-a-byte, PTQ1_0 per-elemento duplicado, fragmento suelto
  "return mul_q8_1..." + un #endif de mas). El spv vecq embebido era VIEJO -> TODO ptq1_0 con
  MMVQ (suite Y decode de produccion) veniaman cayendo en FALLBACK al matvec f32 silenciosamente.
  Por eso todos los env configs empataban siempre. Reparado: archivo = pristine
  prism-b10709-9a9394a + UNA seccion PTQ1_0 region-uniform con loads u32/packed16 anadidos
  (3x u32 + unpack8 por 16 elems; qh via 1 u16). Compila por primera vez; 68/68 correctitud
  (ptq1_0/tq2_0/q2_k/q6_k/q4_0); decode E2E sin cambios (157.1 ms/tok GPU-sum).
- RESULTADO NEGATIVO decisivo: vecq verdadero (int-dot + u32 loads) = 381/231/6771 us en
  gate/up/qkv/lm_head = IDENTICO al matvec f32 LUT y al closed-form. Eliminados como cuello:
  LDS-vs-ALU, byte-vs-u32 loads, f32-vs-q8_1, config pipeline (stdq/sub16). Todos los
  disenos ptq1_0 ~50 GB/s in-suite / ~41 frio; tq2_0 102 frio con la MISMA estructura
  16-hilos-por-bloque.
- Lo que queda aislado: el PATRON DE ACCESO mismo - bloques ptq1_0 de 28 bytes (56 B/warp,
  row stride 1120 B) vs tq2_0 66 bytes (132 B/warp). D2 ronda 2 (sesion propia, no
  micro-tweak): rediseno del walk (32+ elems por hilo, multi-row por thread, o capture RGP).
- Higiene: el reparo hace que cada ninja futuro regenere TODOS los vecq (K-quants vuelven a
  pristine + seccion PTQ1_0). touch mul_mat_vecq.comp para forzar regen. Detalle completo:
  GPU_SPEEDUP_ASSESSMENT_2026-09-22.md "D2 session".

## Handoff D2 ronda 2 a otro agente (2026-09-24 noche)
User cerro todo para reabrir sus apps -> la ventana GPU/RAM de hoy termina. Runbook
autocontenido escrito para el proximo agente: docs/D2_ROUND2_RUNBOOK_2026-09-24.md
(estado verificado, reglas duras C:/99%, loop token-free con comandos exactos, cola de
experimentos E1 pipeline-spec -> E2 elems/hilo -> E3 multi-bloque -> E4 RGP, definition of
done con golden gate --name bonsai2-ptq10, camino negativo documentado). TASKLIST.md tiene
la entrada al tope de la cola. Night runner CATTS-NightJobs (02:30) sigue armado: baseline
limpio + gpu_sweep corren solos; leer MORNING_REPORT.md de data/night/<fecha>/ antes de
tocar la GPU.

## E1 medido + confirm automatico instalado y estrenado (2026-09-24 noche-2)
- E1 STAGED y MEDIDO: env GGML_PTQ1_0_WG (default 32) escala SOLO spec[0]=local_size_x de
  los pipelines matvec ptq1_0 (f32 y vecq; grid math/NUM_ROWS intactos, tmpsh escala con
  BLOCK_SIZE). Resultados: WG=64 EMPATE exacto (396/6819 us); WG=128 -18% en lm_head
  (5595 vs 6805) y gate/up -7% PERO 1 fail de correctitud (m=16 n=1 k=1024, ERR 0.86,
  solo en la 6600, en AMBOS paths f32 y vecq -> estructura compartida; k=1024 = unica shape
  del suite con blocks==it_size). E1b = root-cause de ese caso antes de usar 128. Produccion
  queda en WG=32. Ni WG=64 ni 128 acercan al salto 2.5x -> el walk profundo (E2/E3) sigue
  siendo el camino.
- CONFIRM AUTOMATICO: scripts/wait_gpu_confirm.ps1 + tarea CATTS-GPUConfirm (daily 10:00,
  poll hasta 22:00): espera ventana libre (sin llama-server, puertos libres, RAM >= 4 GB,
  2 polls estables) -> corre perop + golden gate solo, reporte en
  data/confirm/<fecha>/CONFIRM_REPORT.md. Primer run: perop PASS (157.9 ms/tok) + golden
  7/8 (barra >=7/8 OK; diverge = toolcall coin-flip documentado) -> el vecq reparado es
  fidelity-equivalente. Gotchas arreglados: PATH llvm-mingw para el server directo
  (0xC0000139), logs stdout/stderr separados, switch -SkipPerop.
- Captura golden: data/golden/confirm-20260924-183714.json.

## E1b root-cause parcial + clean-baseline intento fallido por contention (2026-09-24 noche-3)
- E1b: el caso que falla a WG=128 es BATCHED: (m=16,n=1,k=1024,**bs=[3,2]**) — caso viejo del
  suite, no de produccion. Descubrimiento OPERATIVO importante: **test mode de
  test-backend-ops CULLEA silenciosamente las shapes grandes** (nada >~m=16/k=1024 corre en
  test mode) -> la correctitud de shapes de PRODUCCION solo se puede portear con
  golden_check, no con el suite. WG=128 pasa 67/68 + las production shapes en perf mode,
  pero su techo es ~5-7% E2E (lm_head=4.2% del decode) -> PARKED; produccion queda WG=32.
  Reabrir solo si E2/E3 requieren wg>32.
- Clean baseline (user cerro apps, "8GB+"): salio 9.28 t/s mean con solo 4.26 GB libres al
  correr (las apps se reabrieron) y practicamente igual que con 2.5 GB (9.36) -> O el piso
  de RAM es mayor que 4 GB, O hay contention del dGPU (user en videollamada con accel de
  video posible). El run de las 02:30 (nada abierto) dira cual. JSON:
  data/profile/d1_20260924-191300.json. Si las 02:30 tambien dan ~9.3, revisar el numero
  12-13 del roster (medido 09-18 evening GPU-exclusive).
- C: en 2.63 GB y bajando (era 3.14) — builds de hoy. Vigilar >=1.5 GB; limpiar zips/temp
  antes del proximo build grande.

## Pregunta AMD/Adrenalin + baseline limpio 7.3GB + agente crawl ENCONTRADO (2026-09-24 noche-4)
- User penso en cerrar/desinstalar "AMD Install Manager" y "Adrenalin" para liberar RAM.
  VEREDICTO MEDIDO: el stack AMD corriendo cuesta ~43 MB (RadeonSoftware 24 + InstallManager
  10 + RSServ 5 + SrcExt 4) — cerrar libera NADA y **desinstalar ROMPE Vulkan** (el driver
  user-mode amdvlk vive dentro de Adrenalin). NO desinstalar. Se detuvo solo
  AMDRyzenMasterSDKTask (cpumetricsserver, metricas CPU) — reversible.
- **AGENTE CRAWL ENCONTRADO**: las tareas "CATTS-GPU-Crawl/-2/-3" + "CATTS-Morning-Ready"
  son one-shots de openclaw (23/09 23:00-23:45 + 24/09 07:10, exit 0) corriendo
  `C:\Users\DevTrivi\.openclaw-autoclaw\workspace\.openclaw\tmp\gpu_crawl_runner.py` — el
  agente perdido del user; finds.txt = su output. Inertes (Next Run N/A), sin conflicto.
- BASELINE LIMPIO 7.3 GB libres (metrics AMD parado, sin videollamada): mean 10.05 t/s
  (9.83/10.26/10.07), loads 129s frio / 13-18s cache-caliente. Curva RAM del dia:
  2.5GB->9.36 | 4.3GB->9.28 | 7.3GB->10.05. La RAM explica ~+7%, NO llega al roster 12-13
  (09-18). Gap restante ~20%: candidato principal = metodo de medicion (roster vs HTTP
  probe con sampling temp0.5/top-p0.85/top-k20 + overhead server) o drift de estado desde
  09-18. El run de las 02:30 (maquina idle total) decide: si da ~10 tambien, re-anchor el
  roster a ~10-11 por HTTP-probe; si da 12+, quedaba algo de contention.
- C: 3.09 GB (el 2.63 era transitorio). Tareas: CATTS-GPU-Crawl* inertes; NightJobs 02:30 y
  GPUConfirm 10:00 armados (GPUConfirm: en dias de videollamadas, borrarla — no ve el
  decode de video del dGPU).


## E2 WIN: int8 LUT — PTQ1_0 6.4 → ~7.4 t/s wall, golden 7/8 intact (2026-09-24 noche-5)
Teoria confirmada: el LUT float de 5 KB en shared tapaba occupancy (~12 wavefronts/CU) y
serializaba cada lookup — incluso con el tensor DENTRO de la Infinity Cache solo daba
52 GB/s (issue-limited, no memory-limited). FIX minimo: LUT como int8 (trit+1 / trit+8 en
vecq) — 5 KB → 1.25 KB — en AMBAS rutas (mul_mat_vec_ptq1_0.comp y mul_mat_vecq.comp).
- Resultados (todo verificado): suite 68/68 (K-quants intactos); GPU-sum decode
  157.8 → **129.2 ms/tok (−18%)**; gate/up 483→377 us, down 470→376, lm_head 6683→5249
  (−20-22% en las 3 familias); wall golden capture **7.44 t/s** (count300 320tok/43s).
- FIDELIDAD: golden **7/8 PASS** (data/golden/confirm-20260924-195613.json) — mismo
  coin-flip toolcall token-0 de siempre; kernels numericamente identicos.
- E2b (zero-LDS closed-form) PARKED: con 1.25 KB el LDS ya no limita.
- IMPORTANTE: los kernels viven SOLO en el build C:/src (llama-server.exe relinkeado 19:54)
  — el runtime de la casa b10685 sigue igual (promocionar = rebuild/distribuir, decision
  del user). GOTCHA del dia: al cambiar shaders hay que relinkear TAMBIEN llama-server
  (ninja llama-server), no solo test-backend-ops, o el server sigue con spv viejos.
- Siguiente palanca (E3): la redundancia de layout (5x re-lectura de bytes por posiciones
  de trit) — repack element-major = lo unico que queda para acercarse a tq2_0 (102 GB/s);
  baseline a vencer: 129.2 ms/tok. Docs: GPU_SPEEDUP_ASSESSMENT "E2 RESULT".

## V-C gate: redundancia DESCARTADA — E3 skipped, ladder barato agotado (2026-09-24 noche-6)
V-C (carga cooperativa: 7 u32 traen los 28 B del bloque a LDS una vez, decode desde LDS —
mata las loads redundantes sin tocar layout): 389/381/145/5599 us = **5% PEOR** que el
int8 directo (339/322/128/5306), 28/28 OK. Las loads redundantes ya eran baratas (L1
dedupe); moverlas a LDS solo agrego barriers. -> **E3 (repack element-major) SKIP** — su
premisa quedo refutada por el gate (ahorro de medio dia).
- Estado final del track shader: PTQ1_0 3.3 → 6.4 (09-22) → **7.4-7.9 t/s** (hoy, int8
  LUT) = +125% en la ruta fiel, golden 7/8 siempre. Banked en C:/src. Restaurado el
  int8 directo como canonical (bak chain en data/shader_baks/).
- Opciones restantes (decision del user): (a) RGP capture (instaler en C: 2.6 GB — riesgoso),
  (b) upstream PR (int8 LUT + vecq repair + metodologia golden + numeros), (c) cerrar el
  track — TQ2_0 (daily driver, 12-13 t/s) no depende de nada de esto.
- El run de las 02:30 corre igual (baseline limpio + primer gpu_sweep data).

## FINDINGS DOC para review (2026-09-24 noche-7)
User pidio escribir los findings del track antes de decidir como cerrar. Documento unico
autocontenido para review: **docs/GPU_TRACK_FINDINGS_2026-09-24.md** (fisica del techo
34.5 t/s, wins con artifacts, hipotesis refutadas una por una, el gap estructural verificado
de TQ2_0 sin int-dot, tabla de decision con costes/token, assessment de cloud = no viable
para medicion Vulkan/RDNA2, reglas de eficiencia de tokens, indice de artifacts). Sesion
siguiente decide desde ese doc: port TQ2_0 int-dot / PR upstream / RGP / cerrar.

## Phase B ejecutado: TQ2_0 int-dot vecq port = EMPATE; ngram spec-decode = sin ganancia (2026-09-24 noche-8)
- Port implementado y VERIFICADO: branch DATA_A_TQ2_0 en mul_mat_vecq_funcs.glsl (get_dm
  ib/8, repack4 byte-alineado 1 u32/16 elems via unpack_q2_0 clonada, mul_q8_1 divisor 2),
  gen tool lista q8_1 + header-filter (DOS listas: spv-gen linea 776 Y header-emission
  linea ~1265 — ambas necesitaban tq2_0), pipeline creation ggml-vulkan.cpp, K_PER_ITER.
  68/68 correctitud. PERO: perf IDENTICO al f32 matvec (131.4 vs 132.5 us gate/up; A/B con
  GGML_VK_DISABLE_MMVQ confirma que vecq corre y empata) -> el int-dot NO acelera TQ2_0.
  La pared de TQ2_0 = coste ALU del decode 2-bit (~1 op/elemento fundamental; q4_0 gana
  porque sus nibbles cuestan 4x menos por elemento, no por int-dot).
- ngram-simple speculative decode en TQ2_0: server decode 12.3-12.8 vs 11.1-12.9 base =
  dentro de ruido en texto realista. (draft-dspark requiere drafter GGUF compatible con
  TQ2_0 — no existe.)
- CONCLUSION DEL TRACK: el techo del daily driver (12-13 t/s) es co-limitado decode-ALU +
  bandwidth; seis familias de variantes medidas sin moverlo. Banked: PTQ1_0 −18% (int8
  LUT, golden 7/8), provenance completa, automatizaciones 0-token. Para 20+ t/s: otro
  quant (menos bpw con decode barato) u otro hardware — documentado, no perseguido.
- Provenance: data/provenance/build-hashes-20260924.txt + suite-log-20260924.txt.
  Doc de review: docs/GPU_TRACK_FINDINGS_2026-09-24.md (actualizado: 7.72 headline,
  gate rule explicita, variance <1%).

## D2 ROUND 2 night session — VECQ WAS DEAD CODE; TQ2_0 int-dot = −44.5% lm_head (2026-09-24 night-9, in progress)

SUPERSEDES the "Phase B EMPATE" entry above: that tie was an artifact — the vecq
pipelines were NEVER DISPATCHED (getter allowlist excluded PTQ1_0/TQ2_0 for b=Q8_1),
so both sides of every A/B ran the f16 matvec. The prior TQ2_0 repack4 was also
layout-WRONG (assumed 4-consecutive-elems/byte; real layout = byte b holds elems
{b, b+32, b+64, b+96} at 2-bit levels).

- Baseline (RAM 7.98 GB, suite 68/68): ptq1_0 lm_head 5322.7 µs (52.6 GB/s) / tq2_0
  2945.6 (111 GB/s) / q4_0 3297.8 (217 GB/s — reference, itself the vecq path).
- E2 (16 elems/thread, 8 threads/block): REGRESSION +12.6% lm_head → reverted. Lesson:
  footprint must come from MORE threads, not more work per thread.
- E3 matrix (env GGML_PTQ1_0_WG × GGML_PTQ1_0_ROWS, both now in ggml-vulkan.cpp):
  ROWS=4 optimal (fewer rows monotonically worse); best = WG=128/ROWS=4:
  lm_head 4854 µs (−8.8%), 28/28. E1's WG=128 failure ROOT-CAUSED: SUBGROUP-reduction
  spv drops cross-subgroup partial sums; WG>64 now auto-selects HYBRID spv (fixed).
  Live default config discovered: WG=64/NUM_ROWS=4/it_size=4 (RX 6600 reports min=max
  subgroup 64 on driver 26.6.2 → fork detects AMD_GCN → rm_stdq=2; E1's "WG=64 tie"
  was therefore a no-op against itself).
- Vecq LIVE wiring: PTQ1_0 + TQ2_0 added to the Q8_1 allowlist (both getters);
  TQ2_0 repack4 rewritten for the real layout (16 consecutive elems = 16 consecutive
  bytes at uniform shift 2·(ib%8 %4); (u32>>shift)&0x03030303 = packed lanes, zero
  unpack work; within-block index bug found via GGML_VK_FORCE_MMVQ and fixed).
- RESULTS (A/B, same build, RAM 6.4 GB): TQ2_0 vecq lm_head 2949 → 1636.8 µs
  (−44.5%, ~200 GB/s = 89% of peak), gate/up 132.6→86.4, qkv 79.4→52.0. PTQ1_0 vecq
  LOSES to its f16 LUT (lm_head 5319→5440) → PTQ1_0 stays f16 by default
  (GGML_PTQ1_0_MMVQ=1 opts in; GGML_TQ2_0_NO_MMVQ reverts TQ2_0).
- Correctness: 68/68 default AND 68/68 with GGML_VK_FORCE_MMVQ (every MUL_MAT through
  vecq — first true dispatch of these branches ever).
- Est. TQ2_0 daily driver: MUL_MAT ~0.64x → GPU-sum ~57 ms/tok → ~16-18 t/s (from
  12-13). Perop capture + PTQ1_0 golden gate + server confirm = NEXT (this session).
- PTQ1_0 headroom banked: WG=128/ROWS=4 −8.8% lm_head (env-gated, suite green).

## CAMPAIGN 23 noches ARMADA (2026-09-25 02:25)
Aprobada por user: campana de medicion 0-tokens hasta el 15/10, luego UNA sesion opus
con el knowledge pack. night_campaign.ps1 (reemplaza a night_jobs como target de
CATTS-NightJobs 02:30; 07:00 stop-guard). Schedule por dia: d1 baseline+sweep+bandwidth,
d2-6 matrices tipo + config axes, d7 baseline, d8-9 spec-decode (+DSpark download A/B),
d10 long-ctx, d11 workload, d12-13 repeats, d14 gap-fill, d15 baseline, d16 RGP,
d17-20 repeats/gaps, d21-23 compile+premortem. Output: data/campaign/<fecha>/ +
knowledge.jsonl + coverage.json + docs/KNOWLEDGE_PACK.md (compiler: campaign_pack.py).
Suite ampliada (rebuild hecho): CPY 1-256MB bandwidth sweep + production shapes n=2,4,8
+ env GGML_VK_DMMV_REDUC (0/1/2 reduction-mode axis). GOTCHA NUEVO: el header de shaders
solo se reescribe en FULL gen mode (sin --source) — al anadir un tipo nuevo correr
vulkan-shaders-gen.exe --output-dir ... --target-hpp ... manual. PENDIENTE para el user:
registrar el prior-art crawl en openclaw (como CATTS-GPU-Crawl) — tarea spec en
data/campaign/prior_art_task.md (por escribir).
## Noche 1 (2026-09-25 02:30): bloqueada correctamente + catch-up manana (2026-09-25 10:00)
- Un llama-server transitorio (PID 51788) estaba vivo a las 02:30 -> los guardas hicieron su
  trabajo: baseline preflight refuse, sweep aborto, nada se contamino. Coverage marco el hueco.
- 3 bugs del script corregidos en el catch-up: PS5.1 utf8-sig (Baseline), Test-Path -and parse,
  guardia 07:00 bloqueaba catch-ups diurnos (nuevo -AllowDay). Y el filtro CPY: las vars usan
  ne_src= (no ne=) y el tool imprime GB/s directo.
- CATCH-UP: baseline 10.25 t/s @5.2 GB (curva RAM: 9.36@2.5 / 9.28@4.3 / 10.05@7.3 / 10.25@5.2
  — el roster 12-13 sigue sin reproducirse de dia; la noche lo dira). **BANDWIDTH CURVE capturada:
  1MB=445, 4MB=585, 16MB=644 (IC), 64MB=183.5, 256MB=184.8 GB/s** — el yardstick real: los
  kernels estan a 56%/37% de la tasa de copia real (185 GB/s), no del pico teorico.
- Sweep pendiente (se auto-repara en noches GapFill — el sistema se auto-cura por diseno).
- GPUConfirm bloqueado hoy (lock) — sus datos ya estaban recolectados.
- Script fixes por verificar en noches siguientes: variance repeats, coverage-driven gapfill.

## Dress rehearsal dia-2 ejecutada (2026-09-25 manana, low-priority)
TypeMatrix-q4_0 corrio completo en BelowNormal (rehearsal, exit 0): PerfCell + celdas
mm:q4_0-* + n-axis regex arreglada (m antes de n en vars). wait-for-GPU anadido (poll 90
min, nunca mata — la clase de fallo de la noche 1 esta cerrada). CATTS-NightJobs Ready
02:30 con SOLO code paths ya ejecutados en daylight. Pendiente rehearsal (noches 8-10):
SpecDecode/LongContext/Workload/RGP/Compile/Premortem — en lunch break o weekend.

## Dress rehearsal COMPLETA (2026-09-25 manana-2): todas las rutas de esta noche ejecutadas
PerfCell arreglado (el parse de MUL_MAT usa MFLOP/GFLOPS; mi regex extendida kB/GB rompia
las celdas mm: — encontrado POR la dress rehearsal, que es su proposito). Rerun: **14 celdas
q4_0 reales grabadas** (7 shapes n=1 + gate/up y lm_head n=2,4,8). Dato clave ya visible:
**batch-2 verification es casi gratis** (gate/up 236.6→237.9 us, lm_head 3312→3325) — la
curva n=1,2,4,8 de los 3 tipos es exactamente lo que opus necesita para spec-decode.
Estado: Bandwidth ✓, TypeMatrix ✓, wait-for-GPU ✓, Record/coverage ✓, tarea Ready 02:30
(dia 2 = Bandwidth + q4_0 repeats = varianza real). Pendiente rehearsal (noches 8-10):
SpecDecode/LongContext/Workload/RGP/Compile/Premortem — lunch/weekend.

## Limpieza de disco (2026-09-25, sesion ZCode)
C: quedo 3.3G libres -> ~40G: hip_tmp_extract borrado, Temp limpia, npm cache clean,
updater installers borrados, recycle bin vaciado, hibernacion OFF (hiberfil 6.2G gone,
reversible con `powercfg /h on`), pagefile auto-off + fijo 8-16 GB (efectivo tras REBOOT,
era 28G auto). NO tocado: hermes (estado vivo de agente), Roaming/npm (CLIs globales),
Cursor/Code caches, C:\zengatrivi (workspace viejo, preserve).

Z: 7.4G -> 66G libres. BORRADO solo duplicados: .git/lfs de
Models/Huihui-Qwen3.8-27B-abliterated (52G; working tree intacto, remote
huihui-ai/Huihui-Qwen3.8-27B-ablitado verificado 200 OK hoy — re-pullable con git lfs pull),
/z/AI/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf (dup de Models/coding, headers
difieren = build distinta, se conservo la de Models/coding), gemma4-coder-q3/.cache
(2.4G download incompleto).

PENDIENTE user (aprobado aun NO dado):
- Superseded (no duplicados): data/models/bonsai27-q1 (3.5G, manifest ->
  prism-ml/Bonsai-27B-gguf@f10afb3 verificado 200) y qwen35-4b (4.3G, ->
  bartowski/Qwen_Qwen3.5-4B-GGUF@4168f45 verificado 200) — re-downloadables con
  sha256 en .manifest.json.
- Juegos reinstalables: Z:\Games\AoE2 DE (40G), D2R Infernal (39G), AoM Retold (1.4G,
  C:\Users\DevTrivi\Games), SC:BW E:\Games (1.3G), Z:\ROMs (18G). Guardar installers
  primero en Z:\Soft/C:\Soft (ya son stash de installers).
- Qwen3.8-27B overlap ~15-25G: elegir serving path ollama (blobs 15.7+10.1G) vs
  llama.cpp quants en Models/coding (IQ4_XS 13.3G no cabe en RX 6600 8G; Q3-DOWN-XS
  y GSQ-IQ2_XS-MTP son los usables). CAUTION: borrar solo el path no usado.
- Z:\CATTS_MeloCache 15G + MeloWrongCache 2G (regenerables, TTS).
- E:\Movies 95G: cursos ZtM 68G, OBS 8.9G, films (Takarajima 8.5G, Iphigenia 1.8G),
  NCIS Sydney S2 2.6G — NO TOCAR PhotosTrufi* y CameraRolle (fotos familia).
- data/models keeper set: bonsai2 x2, neohorse14b-q8, spark25, minicpm5 x2,
  gemma-e4b-qat (granite42-8b-q4 y resto a decision user).

## Task-3 Supervision written (2026-09-25): PTQ1_0 Vulkan next step design
Analyzed knowledge.jsonl (days 1-2) vs track findings: real memcpy BW 185 GB/s reconciles all numbers — TQ2_0 vecq 200 GB/s (89% peak), PTQ1_0 41 GB/s (22% real). Specdec ngram +10% confirmed day 2 (19.3-20.0 vs 17.6-19.1 t/s); night-8 no-gain was likely RAM contention. Next PTQ1_0 design: clone TQ2_0 vecq success (repack4 of REAL layout + int-dot + more threads) but via f32 LUT path (PTQ1_0 vecq loses vs f16 LUT per night-9). Key: WG=128/ROWS=4 banked (E1: -8.8% lm_head) + elements/thread 32 + multi-block walk + SUBGROUP reduction. Target: lm_head cold ≤2800 µs (102 GB/s) + golden 7/8. Written to docs/OPENCODE_TASK3_SUPERVISION_2026-09-25.md with experiment queue, night campaign insertion (d2-6 matrices, RGP day 16), and token-free iteration loop.

## D2 ROUND 3 — Próximos pasos concretos kernel Vulkan custom (2026-09-25, post-supervision)
**Objetivo**: Llevar PTQ1_0 de 7.4-7.9 t/s → ~11.5 t/s fiel (paridad TQ2_0 BW 102 GB/s en lm_head cold ≤2800 µs) sin romper golden 7/8.

**Diseño base (clonar éxito TQ2_0 vecq adaptado a PTQ1_0 f32 LUT):**
1. **REAL layout repack4 en mul_mat_vecq_funcs.glsl PTQ1_0**: byte b guarda elems {b, b+32, b+64, b+96} (shift 2·(ib%8 %4)). 1 u32 = 16 elems consecutivos. Elimina unpack work.
2. **int-dot via q8_1 path**: GGML_PTQ1_0_MMVQ=1 opt-in; divisor 2 para trits. Requiere getter allowlist PTQ1_0 en ggml-vulkan.cpp (ya añadido night-9).
3. **WG=128/ROWS=4** (banked E1: -8.8% lm_head, suite green). SUBGROUP reduction auto-seleccionada para WG>64 (fix night-9).
4. **Elements/thread 32** (doble del actual 16) + **multi-block walk**: cada thread procesa 2 filas consecutivas por iteración (it_size=2), reduciendo row-stride pressure (1120 B → 560 B efectivo).
5. **LUT int8 en shared** (1.25 KB, ya banked E2) — no cambia.

**Loop token-free (iteración ~10 min):**
```
# En C:/src/llama.cpp
# 1. Editar mul_mat_vecq_funcs.glsl (sección PTQ1_0): nuevo repack4 REAL + get_dm 32 elems + mmvq_dot_product int-dot
# 2. Editar mul_mat_vecq.comp PTQ1_0: K_PER_ITER=32, it_size=2, WG=128/ROWS=4 via spec constants
# 3. ninja test-backend-ops (target nombrado, ~2 min)
# 4. Perf en lm_head shape (248320x5120, n=1) — yardstick frío inmune a IC
# 5. Correctness: 68/68 suite + GGML_VK_FORCE_MMVQ=1 (todas MUL_MAT por vecq)
# 6. Si lm_head ≤2800 µs Y suite verde → golden_check --name bonsai2-ptq10 (7/8 bar)
# 7. Si golden PASS → perop capture 1 decode + server confirm
```

**Criterios de parada (definition of done):**
- ✅ lm_head cold ≤2800 µs (≥102 GB/s, paridad TQ2_0)
- ✅ Suite 68/68 default + 68/68 FORCE_MMVQ
- ✅ Golden 7/8 (toolcall coin-flip permitido)
- ✅ Perop PTQ1_0 GPU-sum ≤85 ms/tok (~11.5 t/s)
- ❌ Si 3 diseños seguidos no mueven lm_head <3000 µs → documentar techo y cerrar track PTQ1_0

**Riesgos conocidos:**
- C: 3.3 GB libres — solo `ninja` targets nombrados, limpiar zips/temp antes de build grande
- test-backend-ops test mode CULLEA shapes grandes — corrección de producción SOLO via golden_check
- WG=128 falla en test mode (batched m=16 n=1 k=1024 bs=[3,2]) — producción usa WG=128/ROWS=4 HYBRID spv (ya fix night-9)
- Relink llama-server obligatorio tras cambio de shaders (ninja llama-server, no solo test-backend-ops)

**Integración campaña nocturna (días 2-6):**
- Día 2-3: TypeMatrix PTQ1_0 (q4_0/PTQ1_0/TQ2_0) n=1,2,4,8 + env axes WG×ROWS×ELEMS
- Día 4: Bandwidth microbench CPY 1-256MB + production shapes validation
- Día 6: SpecDecode ngram A/B (TQ2_0 vecq +10% confirmado día 2)
- Día 16: RGP capture (si C: permite installer) para per-instruction truth

**Artefactos de referencia:**
- Supervisión completa: docs/OPENCODE_TASK3_SUPERVISION_2026-09-25.md
- Assessment detallado: docs/GPU_SPEEDUP_ASSESSMENT_2026-09-22.md (secciones D1, D2 prep, D2 session, E2, V-C, Phase B, night-9)
- Runbook D2 ronda 2: docs/D2_ROUND2_RUNBOOK_2026-09-24.md
- Knowledge pack compiler: scripts/campaign_pack.py → docs/KNOWLEDGE_PACK.md (día 23)

## Matvec profile (2026-09-25 14:20, task-3 supervision, sesion ZCode)
- Pedido user: "profile the matvec first" (ref experto 3060: 26->40 t/s). Doc entregable:
  docs/MATVEC_PROFILE_2026-09-25.md. Complementa (no reemplaza) el diseno D2-3 de
  OPENCODE_TASK3_SUPERVISION_2026-09-25.md: refina el ORDEN de ejecucion con datos.
- Datos (MEDIDO, perop post-E2 d1_perop_20260924-231105.json, step 117.7 ms):
  MUL_MAT 90.4% del step; matvec PTQ1_0 = 5.60 GB pesos/token (MLP 67%, attn+GDN 28%,
  lm_head 5%) a 52.7 GB/s efectivos = 28% de la copia real 185 GB/s (techo ~33 t/s);
  referencias: q4_0 217 GB/s, TQ2_0 vecq 200, TQ2_0 walk viejo ~103. Todas las shapes
  de produccion corren 52-58 GB/s (deficit uniforme).
- Perfil por grupo (INFERIDO por eliminacion A/B ya medida): walk/latencia-occupancy
  ~50-55% DOMINANTE (56 B contiguos/warp, row stride 1120 B); LDS-LUT ~8-10% (mitigado
  por E2 int8); ALU ~10% descartada (todas las variantes de computo empatan);
  reduccion/barriers ~8-10% (sin A/B positivo aun); resto loads x (IC-residentes).
- Top-3 optimizaciones (orden de ejecucion): #1 WG=128/ROWS=4 banked + paired-row
  walk (-8.8% ya medido, objetivo step ~95-100 ms = 10-10.5 t/s GPU-sum, riesgo bajo)
  -> #3 vecq PTQ1_0 con repack4 del REAL layout (A/B informativo, cierra pregunta
  vecq; night-9 probablemente perdio por layout asumido equivocado) -> #2 repack
  element-major CONTIGUO (E3 con premisa CORREGIDA: el beneficio es contiguidad, no
  ahorro de loads; unico camino al 50-55% dominante; objetivo 13-16 t/s; sesion
  propia con golden gate 7/8).
- Confirmacion pendiente: RGP capture (dia 16 campana) o VK pipeline-statistics via
  GGML_VK_PERF_LOGGER para convertir la tabla de grupos a MEDIDO; perop capture nueva
  tras activar #1.
- Higiene: SIN modelos levantados, GPU intacta, nada borrado, golden_prompts.json
  intacto. opencode TUI lanzado 13:43 (Windows Terminal, modelo gratis
  nemotron-3-ultra-free) con brief de supervision; PID vivo 110096.

## MATVEC PROFILE Round 2 — Paired-row walk implementado (2026-09-25, día, CPU-only)
- **Cambio**: paired-row walk en `mul_mat_vec_ptq1_0.comp` (cada hilo procesa 2 filas adyacentes, n+=2). Backup: `.bak-20260925`.
- **Config banked activada**: `GGML_PTQ1_0_WG=128` / `GGML_PTQ1_0_ROWS=4` (env-gated, ya en ggml-vulkan.cpp).
- **Correctness**: 68/68 suite PASS (default y WG=128/ROWS=4). TQ2_0/q4_0/q2_k/q6_k sin regresión.
- **Perf A/B (lm_head cold 248320×5120)**:
  - PTQ1_0 f32: baseline 4816 µs → **4799 µs (-0.3%)** con WG=128/ROWS=4 + paired-row
  - TQ2_0 vecq: 2949 → 1642 µs (-44%, night-9 win confirmado)
  - Q4_0: 3298 → 3303 µs (sin cambios)
- **Análisis**: paired-row secuencial (elems-extra en M) **no mejora coalescing**; accesos a activaciones idénticos para ambas filas. Walk real que da paridad TQ2_0 requiere threads-extra (32 hilos/bloque, pares adyacentes → 224 B/warp contiguos) = WG=256.
- **Entregables**: `docs/MATVEC_PROFILE_ROUND2_2026-09-25.md` (diff, comandos noche, criterios, riesgos).
- **Próximo paso (optimización #3)**: vecq PTQ1_0 con repack4 del REAL layout (clon TQ2_0 night-9 corregido) — cierra pregunta vecq, A/B informativo.
- **Pendientes**: golden_check 7/8, perop capture post-config, FORCE_MMVQ=1 correctness, RGP día 16.

## TQ2_0 VECQ PORT = WIN REAL −35% (2026-09-25 tarde): el "empate" del suite era un artefacto IC
Production per-op capturas (d1_perop, C:/src build con el port de anoche): TQ2_0 GPU-sum
81.0 → **53.0 ms/tok (−35%)**; gate/up 210→124.6 us (−41%); lm_head 2802→1582 us =
**193 GB/s cold (clase q4_0)**; wall 13.02 t/s CON logger (~15 sin el, est) vs 10.25
shipped-runtime baseline de ayer. Causalidad: GGML_VK_DISABLE_MMVQ=1 (f32 forzado) = 81.0
-> el vecq int-dot ES la causa. @32K q4 KV: 12.70 t/s wall (el viejo T2 era 10.9).
- LECCION DE METODOLOGIA (asciende veredictos): los empates in-suite NO son empates de
  produccion — IC-warm satura en el mismo plateau issue-limited y enmascara diferencias
  reales. Los seis "empates" quedan demoted a "no probados en produccion"; re-test barato
  = capturas perop con los env toggles. lm_head 193 GB/s cold = streaming clase q4_0
  desde un kernel ternario 2-bit.
- Nota: el wall del roster (12-13) era medicion shipped-runtime; el C:/src build corre
  13.0 CON logger — la promocion del build C:/src a runtime de casa ahora tiene un
  motivo medido (+27% sobre shipped en el daily driver).

## opencode free-tier run LANZADO (2026-09-25 tarde): kernel iteration a 0 cloud tokens
User pidio usar opencode con free-tier models para el heavy lifting del kernel (200M tokens
en la nube sin resultado suficiente a su juicio). Setup: opencode 1.18.32 (npm global) +
Zen auth (big-pickle = free; glm-5.3-flash Zen requiere fondos — descartado). Truco clave:
git init en C:/src/llama.cpp (baseline commit "pre-opencode") — sin git root opencode
resolvia el proyecto como Z:/catts y auto-rechazaba el arbol de shaders como
external_directory. Config C:/src/llama.cpp/opencode.json: model opencode/big-pickle +
permissions edit/bash/external_directory allow, webfetch deny. Brief: TASK.md (meta GPU-sum
53 -> <=45 ms/tok TQ2_0, candidatos NO refutados: non-matmul 12-13 ms, lm_head 193->217,
f16acc, reduc axis; loop verificacion obligatorio ninja -j 2 -> suite 68/68 -> perf
lm_head -> perop; guardrails: sin downloads, sin HIP, baks en Z:). Lanzado en background
BelowNormal (pid cambia — log: C:/src/llama.cpp/opencode-run.log; ITERATION_LOG.md = su
cuaderno). Presupuesto: 6 iteraciones o <=45 ms/tok verificado. NOTA de seguridad: los
"28.6 GB huerfanos" de Z:/ollama eran FALSOS (bug digest-vs-filename en mi verificacion) —
los blobs son 2 modelos Qwen3.8-abliterated REFERENCIADOS; nada se borro. Modelos reales
en Z: inventariados en data/campaign/model_inventory_20260925.md (candidatos delete con
record: coder7 x2, nanbeige, qwen35-4b, gemma4-coder sin eval, granite sin eval ~20 GB;
GSQ-RCO IQ2_XS-MTP de finds.txt YA ESTABA en disco sin testear).

## Spec-decode night results (2026-09-25 tarde-2): TQ2_0 a 20.5 t/s; MTP-lean incompatible (documentado)
- TQ2_0 base (C:/src build, vecq int-dot): server decode **20.5 t/s** en prompt realista
  (17.6-20.5 en 3 probes) — el target de 20 t/s del daily driver ALCANZADO por el vecq port.
  wall 17.6 t/s. ngram: 19.3-20.0 (+10-16% sobre base 17.6 en el run pareado, ruido alto).
- dspark drafter (1.79 GB, SHA verificado 25e73f9f) + TQ2_0: **INCOMPATIBLE** — "failed to
  process speculative batch" (cruce de generaciones Bonsai-1 drafter / Bonsai-2 target).
- PTQ1_0-mtp-lean (6.30 GB, SHA verificado 1e33c571) + draft-mtp: **INCOMPATIBLE con
  nuestro b10709** — el GGUF usa token_embd como latente-Hadamard y nuestro fork lo lee sin
  la inversa: "Hadamard-latent table read without the inverse transform -> failed to create
  MTP context". Requiere el build del autor (rev 285542d, CUDA-linux sm86/89 — no corre
  en RDNA2/Windows). Artifacts en disco esperando patch/port; ngram queda como el unico
  spec-decode funcional (+10-16% medido).
- DIAGNOSTICO de scripts (para el record): el PATH con \t \b interpretados (tab/backspace)
  mato servidores lanzados por python silenciosamente (log vacio = muerte pre-banner);
  foreground + exit code = el diagnostico. d1_perop setea PATH internamente por eso funciono.

## Tweet thread + campaign re-scope (2026-09-25 tarde): "atom by atom" prioridad
User: meta 50 t/s (via spec-decode amortization), insatisfecho hasta inspeccion
"atom-by-atom" de la tarjeta; tesis: AMD hizo soft "good enough" para RDNA2 y abandono —
nuestro trabajo es soft card-specific. Dato ancla: RTX 3060 ~46 t/s en el mismo modelo
(83% BW, REPORTADO — verificar fuente). Draft de 4 tweets listo para posteo:
docs/TWEET_THREAD_2026-09-25.md. Campaign re-scope: RGP capture movida a la noche 3
(antes d16) — C: cleanup + install RGP = prerequisito user. Direccion principal de diseno:
portar el patron q4_0 (nibbles + int-dot, 217 GB/s probado) al decode ternario.
Verificacion del claim 3060 = primera pregunta que el feedback va a hacer.

## RDTS suite instalado + RGP capture rehearsal (2026-09-25 tarde-3)
- La pagina /rdts-windows/ de gpuopen REDIRIGE al zip del suite (393 MB): RDTS-2026-05-28
  PORTABLE extraido en C:/tools/rdts/RadeonDeveloperToolSuite-2026-05-28-1806/ (RGP + RDP
  + PanelCLI + Service + BONUS spirv-as/dis + amdgpu-dis + utils/vulkan — la pregunta
  SPIR-V directo del campaign audit = RESPUESTA: disponible).
- RadeonDeveloperPanelCLI: profiling mode con --rgp-auto-capture=dispatch:N:M (capture por
  dispatch) + clocks mode (telemetria — "Capture API initialized successfully", ve la RX
  6600 ✓). PERO profiling init FALLA: "Failed to initialize capture context/API" — falla el
  init de captura en profiling (driver 32.0.21043 vs RGP 2.7? service no arrancado? modo
  developer?). REHEARSAL llego al 90%: suite ✓, CLI ✓, clocks ✓, server+decode ✓ (con el
  PATH correcto: llvm-mingw SIEMPREprepended — la leccion de los dies silenciosos), falta
  resolver el init de profiling capture. Night-3 RGP slice lo intenta autonoma y marca el
  error especifico. ESTA PENDIENTE: resolucion del profiling init (service? driver mode?).
- GOTCHA de flujos: el capture CLI debe arrancar ANTES del llama-server (registra el
  filtro de proceso; el hook ocurre en la creacion del proceso) y finaliza cuando el
  server termina. El attach a un server ya corriendo NO hookea.

## HANDOFF escrito (2026-09-25 noche): docs/HANDOFF_2026-09-25.md
Handoff unico y autocontenido para cualquier sesion nueva: estado medido (TQ2_0 20.5,
PTQ1_0 7.4-7.9), lo que corre (opencode free, campana noche 2), automations armados,
artifacts (mtp-lean + dspark SHA-verificados, RDTS en C:/tools/rdts, provenance, baks),
decisiones pendientes del user (delete list, fuente 3060, posteo tweets, test mtp-lean),
proximas acciones en orden, gotchas con coste real. Empezar por HANDOFF -> WORKFLOW ->
FINDINGS. SESION CERRADA aqui; el opencode free-run sigue en background y la campana
sigue a las 02:30.
