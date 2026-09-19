# Chores API (HTTP in, local Smol models out)

`scripts/chores_api.py` (stdlib only) + `npm run chores` / `chores:check`.
Superset of `voice_gateway.py` (same chat proxy + CORS).

## Endpoints (default :9111)

- `GET /health` — api ok, server_live, owner (api/other), model.
- `GET /models` — 7 Smol models + loaded flag. Loads nothing.
- `POST /models/load {model, thinking?, context?}` — lift a model to VRAM.
  409 if :9104 busy (SMOL.cmd?). One model at a time.
- `POST /models/stop` — stops the API-owned server only.
- `POST /v1/chat/completions` — streamed chat proxy (OpenAI shape).
- `POST /agent/turn {prompt, project?, max_time?}` — one OMP
  tool turn in an operator-approved project root. Tools are
  `read,grep,glob` (+`write,edit` only with `--allow-writes`);
  bash is never exposed. `approval` is not caller-configurable and
  is rejected in the body. Default project: first `--project-root`.
  Stateless (`--no-session`); multi-turn = repeated calls.

## Security (since 2026-09-16)

- Bearer auth required: `CHORES_API_TOKEN` env (>= 32 chars, no
  spaces); requests without/with a wrong token get 401. Startup
  refuses to run without a token (fails closed).
- Bind is loopback-only (validated); remote access = authenticated
  SSH tunnel, never a LAN bind.
- `project` must be an exact `--project-root` (resolved, existing);
  anything else 403. Default project = first root.
- CORS: no `Access-Control-Allow-Origin: *`; per-origin echo only
  for `--allow-origin` entries.
- Model loads/turns: single-flight lock; body size capped; invalid
  JSON/oversized/TE requests rejected. 500 on turn crash instead of
  hanging the caller.

## Rules

- Single owner: API-owned server blocks SMOL.cmd and vice versa (port).
- Heavy model loads compete with desktop GPU use: gate live loads on
  15 min no-input idle. Cold checks need no gate.
- Journals: `data/chores/runs/` (prompt, stdout, stderr per turn).
- Never auto-starts on boot; nothing persists except journals.
- For browser clients: `--allow-origin https://your.app` and send
  `Authorization: Bearer <token>`; token is stripped from the OMP
  child environment before spawn.
