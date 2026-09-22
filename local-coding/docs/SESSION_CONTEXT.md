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
