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
