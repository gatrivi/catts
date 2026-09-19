# Voice gateway (local models via mic/chat)

Built 2026-09-12, additive only. No STT/prompt-append/endpoint contract touched.

## Pieces

- `scripts/voice_gateway.py` (stdlib only): `GET /health`,
  `POST /v1/chat/completions` streamed passthrough to the smol
  llama-server (`:9104`) + CORS. Loads no model itself.
- challenge-zero `LMStudioChatModal.jsx`: mic button (existing
  `useVoiceToText`/Deepgram) + optional direct POST to the gateway when
  `REACT_APP_VOICE_GATEWAY_URL` is set. Unset = old `/api` path.

## Run

PC: `SMOL.cmd` (load model) + `python scripts/voice_gateway.py --port 9110`.
Phone (tailnet): gateway with `--host <100.x> --port 9110`, open the
dev server over `http://<100.x>:3000`, set gateway URL to
`http://<100.x>:9110`. Use the http dev server, not the https Vercel
deploy (mixed-content blocks http gateway calls).

## Local STT weight (no local STT installed today)

Nothing on disk; Deepgram cloud does STT now (needs internet + key).
If offline STT is wanted later (explicit download OK needed):
whisper.cpp binary ~10-30 MB + models tiny 75 MB / base 150 MB /
small 500 MB, CPU real-time on this Ryzen; or sherpa-onnx binary
~15 MB + streaming model ~200-400 MB, lower latency. Either is
trivial next to the 20 GB models; home on Z:.
