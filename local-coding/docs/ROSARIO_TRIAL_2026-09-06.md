# Rosario local-model trial — FAILED acceptance

2026-09-06. Bounded trial completed: initial attempt plus two repair rounds.
Original Rosario repo preserved: all 1706 snapshot hashes unchanged.
No promotion, push, deployment, dependency installation, model deletion, or default change.

## Outcome

The local 27B model did not complete the bottom-bar task. Two syntactically valid
edit batches changed only BottomNav.jsx and left the functional defects unresolved.
The final repair used three smaller file-specific requests; the batch was rejected
atomically because its first response opened a JSON fence without closing it.
No final-round changes were applied. Do not promote the isolated candidate.

Even if that fence were manually corrected, the final responses fail review:
- CSS keeps the max-width:389px rule hiding Devociones and does not stack arrow labels.
- Booklet publishes rosario-booklet-state, but BottomNav listens to three different
  event names. Its boundary formula also mishandles prayers without inner verses.
- Host did not correct these responses or credit them as model successes.

## Browser baseline and action evidence

Fresh rosario-trial browser, isolated source/dependencies, CSP blocks external
connections. Welcome dismissed. App compiled/rendered with no browser runtime errors.
Evidence: browser-transcript.jsonl, before-*.png, baseline-mas-320.png.

| Action | Observed baseline |
| --- | --- |
| Previous | Pointer at first step inert but enabled; Enter correctly returns from step 2 |
| Next | Pointer advances; final Ángelus 8/8 remains there but enabled |
| Devociones | Pointer and Space open; close works; Ángelus selection works |
| Libro / Volver | Direct devotion load incorrectly says Libro; shelf toggle reveals Volver; clicking Volver still leaves Ángelus after 2 seconds |
| Rosario | Navigates to /rosario |
| Más | Opens; scrim blocks bottom-nav hit targets |
| Diario / Rosedal / Camino | Navigates to /plan, /macetones, /camino |
| Reliquario / Rosa / Voz / Autorezo | Navigates to /reliquias, /rosa, /voz, /cola |

Screenshots: 320x568, 360x800, 390x844, 800x360, 1280x800; simple-mode and
left-handed at 320x568. Baseline and first-attempt browser audit confirm missing
Anterior/Siguiente text and hidden Devociones below390. First-attempt navigation
height remains70px, with actual button center hit targets reachable when overlays close.
The original baseline-320.png was overwritten by a later Más-state capture; use
before-320.png for baseline Libro. after-*.png are FIRST-attempt screenshots,
not screenshots of an accepted final fix.

The full success matrix (every action by pointer AND keyboard, every size in all
accessibility modes) was not completed because acceptance already failed and the
last repair was rejected. final-actions.json is prepared but was NOT executed.

## Validation

- Exact/path checks accepted attempt1 (6 edits) and repair1 (6 edits), each only
  modifying src/components/Navigation/BottomNav.jsx. No unwanted file edits.
- Final repair2 rejected before any file write; repair2-validation.json.
- Production webpack compilation succeeds. Host harness disables ESLint and reads
  the existing installed dependencies; this is not a standard npm build invocation.
  build-result.json records compiler status; build.log records output.
- Existing regressions: 61/62 tests pass, 9/10 suites. Failure:
  devotionsShelfFlow / Ángelus Liber shows devotion chrome after pick, missing visible
  Ángelus title. This test imports unchanged BookletView and does not load BottomNav;
  the failure is in the captured WIP baseline, independent of the sole applied edit.
  See regression-results.json and regression.log. No tests changed or weakened.
- Original integrity: integrity-after.json, 1706 checked, zero changes.

## Measurements

Load means process start to readiness, not a controlled cold-cache benchmark.

| Run | Load s | Request s | Prefill s | Decode tok/s | Minimum available RAM GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| ISTA IQ2_XS-MTP tiny JSON smoke, 52 GPU layers | 130.97 | 32.19 | 22.88 | 1.42 | 5.96 |
| Installed Q3-DOWN-XS 27B, attempt1 | 111.72 | 291.53 | 105.65 | 6.77 | 5.83 |
| Installed 27B, repair1 | 107.03 | 265.34 | 116.37 | 6.86 | 6.39 |
| Installed 27B, repair2 markup | 110.45 shared | 95.47 | 55.06 | 7.19 | 4.57 shared |
| repair2 CSS | same process | 195.98 | 46.00 | 7.51 | same |
| repair2 Booklet | same process | 93.52 | 13.90 | 7.14 | same |

27B used Vulkan1, 56 GPU layers, 8K Q8 KV, MTP draft3, greedy decoding.
ISTA smoke passed the tiny JSON content check but was too slow in this conservative
configuration; no claim that ISTA is universally slower or worse. No fallback deleted.
Three local edit cycles plus smoke consumed roughly24 minutes of load/inference;
browser/setup/validation add overhead. All responses terminated normally, not length-limited.
Raw envelopes did not satisfy the requested JSON-only format. Production parser
accepted complete think/fence wrappers for the first two batches, but rejected the
unclosed final markup fence. No hidden retries or manual JSON repair.

## Host assistance and limits

This was supervised model editing, not a successful autonomous plan/worker/review
workflow. Host reproduced failures, supplied relevant source and event-contract
guidance, ran checks, and reviewed diffs. Final round split into three requests with
no test-feedback loop between them. All application edits are model-generated.

Trial-only validator reuses production parser, path, unique exact-match and edit-count
checks; file-read/output cap raised from32KB to64KB because captured BookletView is
already53KB. Production runner unchanged. Final multi-request batch checked atomically.
Host preview/test/model/browser scripts sit OUTSIDE the isolated project.

Task-owned model servers, preview servers, and rosario-trial browser were stopped.
Model owner.json files record process identities; ports6671/9113 checked closed at finish.
Existing CatTS API was not stopped. Final available RAM sample:8.29GiB.

## Resume

Do not repeat the same repair loop or promote this candidate. The useful next setup
work is validating cross-file event contracts and whole-task coverage before claiming
local independence. A new app-fix attempt requires fresh direction; retain original WIP.
Raw responses, per-run pending journals, diffs, logs and the independent baseline remain here.
