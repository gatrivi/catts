"""
Diagnostics: smoke checks that tell *where* CATTS breaks.

Este módulo ejecuta pasos secuenciales y guarda el resultado en memoria.
El objetivo es que `GET /diagnostics/{id}` muestre:
- qué step falló (error_stage)
- cuánto tardó cada step (elapsed_ms)
- un detalle legible para debug
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
import tempfile
import struct
import wave
import uuid
from pathlib import Path

from api.routes.health import health as health_route
from config import DATA_DIR, STT_MODEL
from db import create_job, create_voice, get_job, job_dir, voice_dir
from services.audio_silence import is_not_silent
from services.stt_client import transcribe_file
from services.translate_client import translate
from services.tts_client import live_tts
from services.voice_trainer import run_voice_training
from services.xtts_tts import worker_status
from services.job_runner import enqueue_audiobook
from services import stt_client, translate_client, xtts_tts


_runs: dict[str, dict] = {}
_lock = asyncio.Lock()


def _new_id() -> str:
    return uuid.uuid4().hex


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _write_sine_wav(out_path: Path, *, duration_sec: float, sr: int = 16000, freq: float = 220.0, amp: float = 0.2) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_sec * sr)
    amp = max(0.0, min(float(amp), 1.0))
    amp_i16 = int(amp * 32767)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n_frames):
            t = i / sr
            v = int(amp_i16 * math.sin(2.0 * math.pi * freq * t))
            wf.writeframesraw(struct.pack("<h", v))
async def _run_step(
    run_id: str,
    step_idx: int,
    step_name: str,
    coro,
    *,
    timeout_sec: float,
):
    step = {
        "idx": step_idx,
        "name": step_name,
        "status": "running",
        "elapsed_ms": None,
        "detail": None,
    }
    async with _lock:
        _runs[run_id]["steps"][step_idx] = step
        _runs[run_id]["updated_at"] = _now_iso()

    t0 = asyncio.get_event_loop().time()
    try:
        detail = await asyncio.wait_for(coro, timeout=timeout_sec)
        elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        step["status"] = "ok"
        step["elapsed_ms"] = elapsed_ms
        step["detail"] = detail
    except asyncio.TimeoutError:
        elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        step["status"] = "failed"
        step["elapsed_ms"] = elapsed_ms
        step["detail"] = f"timeout after {timeout_sec}s"
        _runs[run_id]["error_stage"] = step_name
    except Exception as exc:
        elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        step["status"] = "failed"
        step["elapsed_ms"] = elapsed_ms
        step["detail"] = str(exc)[:400]
        _runs[run_id]["error_stage"] = step_name

    async with _lock:
        _runs[run_id]["steps"][step_idx] = step
        _runs[run_id]["updated_at"] = _now_iso()


async def _stop_if_failed(run_id: str, step_name: str) -> bool:
    run = _runs.get(run_id) or {}
    if run.get("error_stage"):
        return True
    return False


async def run_smoke() -> str:
    run_id = _new_id()
    async with _lock:
        _runs[run_id] = {
            "id": run_id,
            "status": "running",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "error_stage": None,
            "steps": [],
        }

    # Pre-create step slots so the UI can poll consistently
    steps = [
        "health",
        "translate",
        "stt_transcribe",
        "voice_train",
        "audiobook_job_audio",
        "audio_decode_peak_check",
        "tts_live",
    ]
    async with _lock:
        _runs[run_id]["steps"] = [
            {
                "idx": i,
                "name": s,
                "status": "pending",
                "elapsed_ms": None,
                "detail": None,
            }
            for i, s in enumerate(steps)
        ]
        _runs[run_id]["started_at"] = _now_iso()

    async def _worker():
        with tempfile.TemporaryDirectory(prefix=f"catts_diag_{run_id[:8]}_") as td:
            tmp_dir = Path(td)

            voice_id: str | None = None
            job_id: str | None = None

            try:
                # health
                async def _health():
                    # health_route requires no API key; it checks worker reachability and readiness.
                    return (await health_route()).model_dump()

                await _run_step(run_id, 0, "health", _health(), timeout_sec=10.0)
                if _runs[run_id].get("error_stage"):
                    return

                # translate
                def _translate():
                    if not translate_client.available():
                        return {"skipped": True, "reason": "translate not installed"}
                    out = translate("Hello world", "en", "es")
                    return {"skipped": False, "text_preview": out[:80]}

                await _run_step(run_id, 1, "translate", asyncio.to_thread(_translate), timeout_sec=60.0)
                if _runs[run_id].get("error_stage"):
                    return

                # stt_transcribe
                async def _stt():
                    if not stt_client.available():
                        return {"skipped": True, "reason": "STT not installed"}
                    wav = tmp_dir / "stt_test.wav"
                    _write_sine_wav(wav, duration_sec=0.9, amp=0.25)
                    result = await transcribe_file(wav, lang="en")
                    # Accept empty transcript as long as we get a response.
                    return {
                        "skipped": False,
                        "language": result.get("language"),
                        "text_preview": (result.get("text") or "")[:80],
                        "stt_model": STT_MODEL,
                    }

                await _run_step(run_id, 2, "stt_transcribe", _stt(), timeout_sec=120.0)
                if _runs[run_id].get("error_stage"):
                    return

                # voice_train
                async def _voice_train():
                    # Create a minimal voice sample (so XTTS has reference.wav).
                    nonlocal voice_id
                    sample = tmp_dir / "voice_sample.wav"
                    _write_sine_wav(sample, duration_sec=1.2, amp=0.25, freq=200.0)
                    voice_id = create_voice("Smoke Voice", "en", str(sample))
                    # Ensure sample ends up in the voice folder under the expected name
                    vdir = voice_dir(voice_id)
                    dest = vdir / "sample.wav"
                    shutil.copyfile(sample, dest)
                    # Training pipeline (stub when WORKER_URL empty)
                    await run_voice_training(voice_id)
                    return {"skipped": False, "voice_id": voice_id, "voice_folder": str(vdir.resolve())}

                await _run_step(run_id, 3, "voice_train", _voice_train(), timeout_sec=180.0)
                if _runs[run_id].get("error_stage"):
                    return

                # audiobook_job_audio (create job + enqueue)
                async def _create_and_wait_job():
                    nonlocal job_id
                    if voice_id is None:
                        raise RuntimeError("voice_id missing")

                    meta = {
                        "title": "Smoke Book",
                        "author": "CATTS",
                        "chapter_mode": "number",
                        "generate_audio": True,
                        "lang": "en",
                    }
                    job_id = create_job("audiobook", voice_id=voice_id, lang="en", meta=meta)
                    jdir = job_dir(job_id)
                    (jdir / "input.txt").write_text(
                        "This is a short smoke test book.\n\nChapter 1\nThis tiny chapter is here to validate the audiobook pipeline.",
                        encoding="utf-8",
                    )
                    # Kick background pipeline
                    await enqueue_audiobook(job_id)

                    # Wait for completion.
                    deadline = asyncio.get_event_loop().time() + 180.0
                    while True:
                        j = get_job(job_id) or {}
                        status = j.get("status")
                        if status in ("done", "failed", "cancelled"):
                            return {"status": status, "job_id": job_id, "message": j.get("message"), "error": j.get("error")}
                        if asyncio.get_event_loop().time() > deadline:
                            raise TimeoutError("audiobook job timed out")
                        await asyncio.sleep(1.5)

                await _run_step(run_id, 4, "audiobook_job_audio", _create_and_wait_job(), timeout_sec=190.0)
                if _runs[run_id].get("error_stage"):
                    return

                # audio_decode_peak_check
                async def _peak_check():
                    if not job_id:
                        raise RuntimeError("job_id missing")
                    jdir = job_dir(job_id)
                    # Chapter 1 should exist if job produced any audio.
                    audio = jdir / "audio" / "chapter_001.mp3"
                    if not audio.exists():
                        audio = jdir / "audio" / "chapter_001.wav"
                    if not audio.exists():
                        raise RuntimeError("chapter_001 audio missing")
                    ok, peak = is_not_silent(audio)
                    if not ok:
                        raise RuntimeError(f"audio seems silent (peak={peak:.4f} < threshold)")
                    return {"audio_file": str(audio.resolve()), "peak": peak}

                await _run_step(run_id, 5, "audio_decode_peak_check", _peak_check(), timeout_sec=30.0)
                if _runs[run_id].get("error_stage"):
                    return

                # tts_live (only when XTTS worker is hot/ready)
                async def _tts_live():
                    if not voice_id:
                        raise RuntimeError("voice_id missing")
                    st = worker_status()
                    if not st.get("installed"):
                        return {"skipped": True, "reason": "XTTS not installed"}
                    if not st.get("ready"):
                        return {"skipped": True, "reason": "XTTS not hot/ready yet"}

                    # Resolve reference audio created by stub training.
                    vdir = voice_dir(voice_id)
                    ref = vdir / "reference.wav"
                    if not ref.exists():
                        ref = vdir / "sample.wav"
                    if not ref.exists():
                        raise RuntimeError("reference wav missing for live tts")

                    audio_bytes, eng = await live_tts("Hello this is a CATTS test", voice_id, "en", ref_audio=ref)
                    out = tmp_dir / "live_test.wav"
                    out.write_bytes(audio_bytes)
                    ok, peak = is_not_silent(out)
                    if not ok:
                        raise RuntimeError(f"live tts audio seems silent (peak={peak:.4f})")
                    return {"engine": eng, "peak": peak, "bytes": len(audio_bytes)}

                await _run_step(run_id, 6, "tts_live", _tts_live(), timeout_sec=120.0)
            finally:
                async with _lock:
                    run = _runs.get(run_id)
                    if run:
                        run["status"] = "done"
                        run["finished_at"] = _now_iso()

    asyncio.create_task(_worker())
    return run_id


def get_run(run_id: str) -> dict | None:
    return _runs.get(run_id)

