"""Runtime TTS engine selection (compare engines without editing .env)."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.deps import require_api_key
from api.schemas import SpeakTTSRequest
from services import fish_tts, kokoro_tts, melotts_tts
from services.tts_client import engine_label, synthesize
from services.tts_runtime import clear_override, get_engine, list_engines, set_engine

router = APIRouter(prefix="/tts", tags=["tts"])


class EngineInfo(BaseModel):
    id: str
    label: str
    configured: bool
    needs_server: bool = False
    clone: bool = False
    note: str = ""
    active: bool = False
    ready: bool = False


class EnginesResponse(BaseModel):
    active: str
    default_from_env: str
    engines: list[EngineInfo]


class SetEngineRequest(BaseModel):
    engine: str = Field(..., min_length=2, max_length=32)


class SetEngineResponse(BaseModel):
    active: str
    message: str


@router.get("/engines", response_model=EnginesResponse)
async def tts_engines(_: None = Depends(require_api_key)) -> EnginesResponse:
    from config import TTS_ENGINE

    rows = list_engines()
    active_engine = get_engine()
    out: list[EngineInfo] = []
    for row in rows:
        ready = bool(row.get("ready_hint", False))
        eid = row["id"]
        if eid == "fish":
            # Fish probes can take several seconds when its server is off. Probe
            # only when selected; inactive engines remain selectable.
            ready = await fish_tts.ready() if row["configured"] and eid == active_engine else False
        elif eid == "kokoro":
            ready = await kokoro_tts.ready() if row["configured"] else False
        elif eid == "melotts":
            # Pure in-memory/process probe; never wait for the model to load.
            ready = bool(melotts_tts.worker_status().get("ready"))
        elif eid == "edge":
            ready = True
        elif eid == "gptsovits":
            ready = bool(row["configured"])
        elif eid in ("xtts", "pocket", "chatterbox"):
            ready = bool(row.get("ready_hint", row["configured"]))
        out.append(
            EngineInfo(
                id=eid,
                label=row["label"],
                configured=row["configured"],
                needs_server=row.get("needs_server", False),
                clone=row.get("clone", False),
                note=row.get("note") or "",
                active=row.get("active", False),
                ready=ready,
            )
        )
    return EnginesResponse(active=get_engine(), default_from_env=TTS_ENGINE, engines=out)


@router.put("/engine", response_model=SetEngineResponse)
async def tts_set_engine(req: SetEngineRequest, _: None = Depends(require_api_key)) -> SetEngineResponse:
    try:
        active = set_engine(req.engine)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return SetEngineResponse(active=active, message=f"TTS engine set to {active} (runtime; .env unchanged)")


@router.delete("/engine", response_model=SetEngineResponse)
async def tts_clear_engine(_: None = Depends(require_api_key)) -> SetEngineResponse:
    active = clear_override()
    return SetEngineResponse(active=active, message=f"Cleared override — using .env default ({active})")


@router.post("/speak")
async def tts_speak(req: SpeakTTSRequest, _: None = Depends(require_api_key)):
    """Text → WAV using the selected engine; MeloTTS accepts Spanish only."""
    # ponytail: reuse live-path ref resolver so clone engines get gaston/default voice
    from api.routes.health import _resolve_ref_audio
    from services.voice_default import resolve_default_voice_id

    eng = get_engine()
    voice_id = req.voice_id or resolve_default_voice_id()
    ref_audio = None
    if eng in ("chatterbox", "xtts", "pocket") and voice_id:
        ref_audio = _resolve_ref_audio(voice_id, engine=eng)

    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "speak.wav"
        try:
            await synthesize(req.text, out, voice_id=voice_id, lang=req.lang, ref_audio=ref_audio)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(500, f"TTS failed: {exc}") from exc
        audio = out.read_bytes()
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "X-TTS-Latency-Ms": str(elapsed_ms),
            "X-TTS-Engine": engine_label(),
            "X-TTS-Lang": req.lang,
            **({"X-TTS-Voice": voice_id} if voice_id else {}),
        },
    )
