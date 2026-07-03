"""Voice training job wrapper — delegates to GPU worker."""

import logging
import shutil
from pathlib import Path

import httpx

from config import WORKER_URL
from db import update_voice, voice_dir
from services.voice_labels import sync_voice_labeled_files

logger = logging.getLogger(__name__)


async def run_voice_training(voice_id: str) -> None:
    vdir = voice_dir(voice_id)
    sample = None
    for ext in ("sample.wav", "sample.mp3", "sample.m4a", "sample.ogg", "sample.webm"):
        candidate = vdir / ext
        if candidate.exists():
            sample = candidate
            break
    if not sample:
        update_voice(voice_id, status="failed", progress=0, message="No sample audio found", error="missing_sample")
        return

    update_voice(voice_id, status="training", progress=5, message="Preparing training data")

    if not WORKER_URL:
        # Stub: copy sample as reference artifact for dev pipeline
        artifact = vdir / "reference.wav"
        shutil.copy(sample, artifact)
        update_voice(
            voice_id,
            status="ready",
            progress=100,
            message="Ready — preview sample saved",
            artifact_path=str(artifact),
        )
        sync_voice_labeled_files(voice_id)
        try:
            from services.voice_ref import prepare_xtts_reference
            prepare_xtts_reference(artifact)
        except Exception:
            logger.exception("Could not build XTTS reference clip for %s", voice_id)
        return

    try:
        async with httpx.AsyncClient(timeout=3600.0) as client:
            with open(sample, "rb") as f:
                files = {"sample": (sample.name, f, "audio/wav")}
                data = {"voice_id": voice_id}
                update_voice(voice_id, progress=10, message="Uploading to worker")
                r = await client.post(f"{WORKER_URL}/voices/train", files=files, data=data)
                r.raise_for_status()
                result = r.json()

        artifact = vdir / "model"
        artifact.mkdir(exist_ok=True)
        update_voice(
            voice_id,
            status="ready",
            progress=100,
            message="Voice training complete",
            artifact_path=str(artifact),
        )
        sync_voice_labeled_files(voice_id)
        logger.info("Voice %s trained: %s", voice_id, result)
    except Exception as exc:
        logger.exception("Voice training failed for %s", voice_id)
        update_voice(
            voice_id,
            status="failed",
            progress=0,
            message="Training failed",
            error=str(exc),
        )
