"""Phone voice hub routes — hold-to-talk STT → project → chat/inbox → Edge TTS."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.deps import require_api_key
from services import stt_client, voice_hub

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/projects")
async def voice_projects(_: None = Depends(require_api_key)):
    return {
        "default": voice_hub.default_project_id(),
        "projects": voice_hub.list_projects(),
    }


@router.post("/turn")
async def voice_turn(
    audio: UploadFile = File(...),
    project: str | None = Form(None),
    lang: str | None = Form("es"),
    _: None = Depends(require_api_key),
):
    if not stt_client.available():
        raise HTTPException(503, "STT not installed — pip install faster-whisper in .venv")
    lang_use = (lang or "es").strip().lower()
    if lang_use not in ("en", "es", "auto", ""):
        raise HTTPException(400, "lang must be en|es|auto")
    stt_lang = None if lang_use in ("", "auto") else lang_use

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = Path(tmp.name)
        try:
            result = await stt_client.transcribe_file(tmp_path, lang=stt_lang)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        transcript = (result.get("text") or "").strip()
        detected = result.get("language") or lang_use or "es"
        if not transcript:
            raise HTTPException(400, "Empty transcript — hold longer / speak closer")

        try:
            proj, intent, user_text = voice_hub.resolve_turn(transcript, project)
        except RuntimeError as exc:
            raise HTTPException(500, str(exc)) from exc

        reply_lang = detected if detected in ("en", "es") else ("en" if lang_use == "en" else "es")

        if intent == "code":
            voice_hub.append_inbox(
                proj["id"],
                voice_hub.inbox_payload(proj, transcript, user_text),
            )
            reply = voice_hub.code_ack(proj, reply_lang)
        else:
            reply = await voice_hub.chat_reply(proj, user_text, reply_lang)

        try:
            wav = await voice_hub.speak_edge(reply, reply_lang)
        except Exception as exc:
            raise HTTPException(503, f"TTS failed: {exc}") from exc

        return {
            "project": proj["id"],
            "label": proj.get("label"),
            "worker": proj.get("worker"),
            "intent": intent,
            "transcript": transcript,
            "user_text": user_text,
            "reply": reply,
            "lang": reply_lang,
            "audio_mime": "audio/wav",
            "audio_b64": voice_hub.b64_audio(wav),
        }
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
