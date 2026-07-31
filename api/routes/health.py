import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from api.deps import require_api_key
from api.schemas import HealthResponse, LiveTTSRequest
from config import OCR_BATCH, OCR_ENGINE, OCR_FAST, WORKER_URL
from db import get_voice, voice_dir
from services import fish_tts, kokoro_tts, melotts_tts, pocket_tts, stt_client, translate_client
from services.ocr_client import check_worker_health
from services.tts_client import engine_label, live_tts
from services.voice_default import resolve_default_voice_id
from services.voice_ref import prepare_xtts_reference
from services.xtts_tts import worker_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    worker_ok = await check_worker_health()
    xtts = worker_status()
    tts_engine = engine_label()
    tts_ready = False
    tts_message = ""
    if tts_engine == "xtts":
        tts_ready = xtts.get("ready", False)
        tts_message = xtts.get("message", "")
    elif tts_engine == "pocket":
        tts_ready = pocket_tts.ready()
        tts_message = pocket_tts.status_message()
    elif tts_engine == "edge":
        tts_ready = True
    elif tts_engine == "fish":
        tts_ready = await fish_tts.ready()
        tts_message = fish_tts.status_message(tts_ready)
    elif tts_engine == "gptsovits":
        tts_ready = bool(WORKER_URL)
    elif tts_engine == "kokoro":
        tts_ready = await kokoro_tts.ready()
        tts_message = kokoro_tts.status_message(tts_ready)
    elif tts_engine == "melotts":
        status = melotts_tts.worker_status()
        tts_ready = bool(status.get("ready"))
        tts_message = status.get("message") or "MeloTTS status unavailable"
    elif tts_engine == "chatterbox":
        from services import chatterbox_tts

        tts_ready = chatterbox_tts.available()
        tts_message = "Chatterbox installed (CPU)" if tts_ready else "pip install chatterbox-tts"
    return HealthResponse(
        status="ok",
        worker_reachable=worker_ok,
        worker_url=WORKER_URL or "(not set)",
        ocr_engine=OCR_ENGINE,
        ocr_fast=OCR_FAST,
        ocr_batch=OCR_BATCH,
        tts_engine=tts_engine,
        tts_ready=tts_ready,
        tts_message=tts_message,
        stt_engine="whisper" if stt_client.available() else "none",
        translate_ready=translate_client.available(),
        default_voice_id=resolve_default_voice_id(),
        xtts_installed=xtts["installed"],
        xtts_ready=xtts["ready"],
        xtts_message=xtts["message"],
    )


def _resolve_ref_audio(voice_id: str, engine: str | None = None) -> Path | None:
    """Chatterbox gets full PCM wav; XTTS gets energy-picked clips."""
    from services.voice_ref import prepare_playable_wav

    voice = get_voice(voice_id)
    if not voice:
        return None
    candidates: list[Path] = []
    if voice.get("artifact_path"):
        ref = Path(voice["artifact_path"])
        if ref.is_file():
            candidates.append(ref)
        elif ref.is_dir():
            nested = ref / "reference.wav"
            if nested.is_file():
                candidates.append(nested)
    vdir = voice_dir(voice_id)
    for name in (
        "fish_ref_en_15s.wav",
        "fish_ref_es_15s.wav",
        "fish_ref_15s.wav",
        "fish_ref.wav",
        "chatterbox_ref.wav",
        "reference.wav",
        "sample.wav",
        "reference_pcm.wav",
    ):
        p = vdir / name
        if p.is_file():
            candidates.append(p)
    if not candidates:
        return None
    if (engine or "") == "fish":
        preferred_names = {
            "fish_ref_en_15s.wav",
            "fish_ref_es_15s.wav",
            "fish_ref_15s.wav",
            "fish_ref.wav",
        }
        preferred = next((c for c in candidates if c.name in preferred_names), None)
        src = preferred or max(candidates, key=lambda p: p.stat().st_size)
        return prepare_playable_wav(src, src.parent / f"{src.stem}_pcm.wav")
    preferred = next((c for c in candidates if c.name == "chatterbox_ref.wav"), None)
    src = preferred or max(candidates, key=lambda p: p.stat().st_size)
    wav = prepare_playable_wav(src, src.parent / f"{src.stem}_pcm.wav")
    if (engine or "") == "xtts":
        return prepare_xtts_reference(wav)
    return wav


@router.post("/tts/live")
async def tts_live(req: LiveTTSRequest, _: None = Depends(require_api_key)):
    tts_engine = engine_label()
    max_words = 80 if tts_engine in {"kokoro", "melotts", "chatterbox", "edge", "fish", "pocket"} else 12
    words = req.text.split()
    if len(words) > max_words:
        raise HTTPException(400, f"Live TTS limited to {max_words} words")
    voice_id = req.voice_id or resolve_default_voice_id()
    ref_audio = None
    if tts_engine in {"xtts", "pocket", "chatterbox", "fish"}:
        if not voice_id:
            raise HTTPException(400, "No voice — save a voice sample first")
        try:
            ref_audio = _resolve_ref_audio(voice_id, engine=tts_engine)
        except Exception as exc:
            raise HTTPException(400, f"Bad reference audio: {exc}") from exc
        if not ref_audio and tts_engine == "fish":
            try:
                ref_audio = fish_tts.resolve_fish_ref(lang=req.lang, voice_id=voice_id)
            except RuntimeError as exc:
                raise HTTPException(400, str(exc)) from exc
        if not ref_audio:
            raise HTTPException(
                400,
                "No reference audio for this voice — open Train voice and save a sample",
            )
        if tts_engine == "xtts":
            xtts = worker_status()
            if not xtts.get("ready", False):
                raise HTTPException(503, xtts.get("message") or "XTTS is not ready")
        if tts_engine == "chatterbox":
            from services import chatterbox_tts

            if not chatterbox_tts.available():
                raise HTTPException(503, "chatterbox-tts not installed")
        if tts_engine == "pocket":
            if not pocket_tts.available():
                raise HTTPException(503, "pocket-tts not installed")
        if tts_engine == "fish":
            if not fish_tts.configured():
                raise HTTPException(503, "Fish Speech not configured — set CATTS_FISH_URL")
            if not await fish_tts.ready():
                raise HTTPException(503, fish_tts.status_message(False))
    elif tts_engine == "kokoro":
        from services import kokoro_tts

        if not kokoro_tts.configured():
            raise HTTPException(503, "Kokoro not configured — set CATTS_KOKORO_URL")
        if not await kokoro_tts.ready():
            raise HTTPException(503, kokoro_tts.status_message(False))
    elif tts_engine == "melotts":
        if req.lang != "es":
            raise HTTPException(400, "MeloTTS supports Spanish only")
        if not melotts_tts.available():
            raise HTTPException(503, "MeloTTS is not installed")
    t0 = time.perf_counter()
    try:
        audio, engine_used = await live_tts(req.text, voice_id or "", req.lang, ref_audio=ref_audio)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"TTS failed: {exc}") from exc
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "X-TTS-Latency-Ms": str(elapsed_ms),
            "X-TTS-Engine": engine_used,
        },
    )
