# Operating ladder — user → paid → free → local → scripts → GPU (2026-09-25)

The cost-ordered intelligence cascade for the GPU/kernel track (and any similar
work). Intent flows DOWN, evidence flows UP. Each layer only does what the one
below it cannot.

```
USER          intent, priorities, go/no-go          (words)
PAID          judgment: goals, specs, final verdicts (e.g. 200-500K/session)
FREE          volume iteration with an oracle        (opencode/Cline, 0 extra cost)
LOCAL         on-device agents, drafting, leg work   (openclaw crawls, hub models, 0)
SCRIPTS       deterministic gates + measurements     (night campaign, verify loop, 0)
GPU           ground truth                           (suite, perf, perop, golden)
```

## The contracts (what makes it work)
- **Paid → Free:** a written brief (TASK.md pattern): goal with numbers, the
  refuted list (never re-test), the mandatory verify loop, stop conditions,
  guardrails. Spec-first — pre-written by the paid layer so the free layer
  never explores blind.
- **Free → Local:** the agent only orchestrates; heavy local work = its own
  scripts/tools (openclaw for web crawls, the hub for model serving).
- **Local/Scripts → GPU:** fixed commands, named targets, one oracle per claim:
  suite = correctness, lm_head perf = cold-true speed, perop = production
  breakdown, golden 7/8 = fidelity. **In-suite ties are not production ties**
  (IC-warm masking) — production perop is the only speed oracle.
- **Evidence flows UP as verdicts**, not dumps: ITERATION_LOG, knowledge.jsonl,
  MORNING_REPORT — the paid layer reads 5-line verdicts, never raw logs.

## Rules learned the hard way
1. Every night/slice gets a daylight rehearsal the same day it's written —
   untested scripts waste nights (night 1 cost: 3 bugs + a blocked run).
2. Measurements are automated and zero-token (CATTS-NightJobs 02:30,
   GPUConfirm 10:00); agents never do what a script can.
3. The paid layer appears at: goal-setting, spec-writing, and the final
   verdict. Free/local layers never make judgment calls on correctness gates —
   the oracle scripts do.
4. Escalate UP on: red correctness gate twice, a refuted premise, an anomaly
   the oracle can't classify. Deescalate DOWN on: anything mechanical.
5. Nothing runs that wasn't rehearsed; nothing is deleted without a
   verified-to-be-safe report; nothing is claimed without an artifact path.

## Current instantiation
- Paid: this session (spec + TASK.md + findings doc) → next: the one-shot
  kernel run reading the Oct-15 knowledge pack.
- Free: `opencode/big-pickle` iterating TQ2_0 kernels (TASK.md, BelowNormal).
- Local: openclaw prior-art crawl (task spec in `data/campaign/prior_art_task.md`).
- Scripts: `night_campaign.ps1` (23 nights, 02:30), verify loop, campaign_pack.
- GPU: RX 6600 via suite/perf/perop/golden.
