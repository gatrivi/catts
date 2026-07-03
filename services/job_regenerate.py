"""Regenerate audiobook audio from an existing manuscript."""

import json
import shutil
from pathlib import Path

from db import get_job, job_dir, update_job
from services.job_runner import enqueue_audiobook


def _clear_audio_outputs(jdir: Path) -> None:
    audio = jdir / "audio"
    if audio.exists():
        shutil.rmtree(audio)
    for name in (
        "audiobook.m4b",
        "audiobook.zip",
        "combined.wav",
        "combined.m4a",
        "ffmetadata.txt",
        "concat_list.txt",
    ):
        p = jdir / name
        if p.exists():
            p.unlink()
    for p in jdir.glob("*--audiobook.m4b"):
        p.unlink(missing_ok=True)


async def regenerate_job_audio(job_id: str, voice_id: str | None = None) -> None:
    job = get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    jdir = job_dir(job_id)
    if not (jdir / "chapters.json").exists():
        raise ValueError("No manuscript — run full job first")

    fields: dict = {
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "message": "Queued to regenerate audio",
        "error": None,
    }
    if voice_id:
        fields["voice_id"] = voice_id
    update_job(job_id, **fields)

    meta = json.loads(job.get("meta_json") or "{}")
    meta["generate_audio"] = True
    meta["audio_only"] = True
    update_job(job_id, meta=meta)

    _clear_audio_outputs(jdir)
    await enqueue_audiobook(job_id)
