"""Sample stats + STT script-match for voice cards."""

from __future__ import annotations

import json
import logging
import re
import wave
from pathlib import Path

from db import get_voice, voice_dir
from services.voice_scripts import script_for

logger = logging.getLogger(__name__)

QUALITY_FILE = "quality.json"


def find_sample(vdir: Path) -> Path | None:
    if not vdir.is_dir():
        return None
    for p in sorted(vdir.glob("*_sample.*")):
        if not p.name.startswith("sample."):
            return p
    for name in ("sample.wav", "sample.webm", "sample.mp3", "sample.m4a", "sample.ogg"):
        p = vdir / name
        if p.is_file():
            return p
    return None


def sample_duration_sec(path: Path) -> float | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wf:
            return round(wf.getnframes() / float(wf.getframerate() or 1), 1)
    except Exception:
        return None


def _tokens(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"\[.*?\]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return [t for t in text.split() if len(t) > 1]


def script_match_score(transcript: str, script: str) -> float:
    """Token recall of script words found in transcript (0–100)."""
    script_toks = _tokens(script)
    if not script_toks:
        return 0.0
    hyp = set(_tokens(transcript))
    if not hyp:
        return 0.0
    hit = sum(1 for t in script_toks if t in hyp)
    return round(100.0 * hit / len(script_toks), 1)


def match_label(score: float | None) -> str:
    if score is None:
        return "not checked"
    if score >= 70:
        return "good match"
    if score >= 40:
        return "partial match"
    return "weak match"


def load_quality(voice_id: str) -> dict:
    path = voice_dir(voice_id) / QUALITY_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_quality(voice_id: str, data: dict) -> None:
    vdir = voice_dir(voice_id)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / QUALITY_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")


def sample_stats(voice_id: str) -> dict:
    vdir = voice_dir(voice_id)
    sample = find_sample(vdir)
    q = load_quality(voice_id)
    if not sample:
        return {
            "has_sample": False,
            "sample_bytes": None,
            "sample_duration_sec": None,
            "script_match": q.get("script_match"),
            "script_match_label": match_label(q.get("script_match")),
            "transcript_preview": q.get("transcript_preview"),
            "quality_status": "missing",
        }
    duration = sample_duration_sec(sample)
    status = q.get("quality_status") or ("ok" if q.get("script_match") is not None else "unchecked")
    return {
        "has_sample": True,
        "sample_bytes": sample.stat().st_size,
        "sample_duration_sec": duration if duration is not None else q.get("sample_duration_sec"),
        "script_match": q.get("script_match"),
        "script_match_label": match_label(q.get("script_match")),
        "transcript_preview": q.get("transcript_preview"),
        "quality_status": status,
    }


async def evaluate_voice(voice_id: str) -> dict:
    """Transcribe sample with STT and score against training script."""
    voice = get_voice(voice_id)
    if not voice:
        raise ValueError("Voice not found")
    sample = find_sample(voice_dir(voice_id))
    if not sample:
        data = {
            "quality_status": "missing",
            "script_match": None,
            "transcript_preview": None,
            "error": "no sample",
        }
        save_quality(voice_id, data)
        return {**sample_stats(voice_id), **data}

    save_quality(
        voice_id,
        {
            **load_quality(voice_id),
            "quality_status": "checking",
            "sample_duration_sec": sample_duration_sec(sample),
        },
    )

    from services import stt_client

    if not stt_client.available():
        data = {
            "quality_status": "error",
            "error": "STT not installed",
            "sample_duration_sec": sample_duration_sec(sample),
            "sample_bytes": sample.stat().st_size,
        }
        save_quality(voice_id, data)
        return {**sample_stats(voice_id), **data}

    lang = (voice.get("lang") or "en")[:2]
    try:
        result = await stt_client.transcribe_file(sample, lang=lang)
        transcript = (result.get("text") or "").strip()
        script = script_for(lang)
        score = script_match_score(transcript, script)
        data = {
            "quality_status": "ok" if score >= 40 else "weak",
            "script_match": score,
            "transcript_preview": transcript[:280],
            "sample_duration_sec": sample_duration_sec(sample),
            "sample_bytes": sample.stat().st_size,
            "language": result.get("language") or lang,
        }
        save_quality(voice_id, data)
        return {**sample_stats(voice_id), **data}
    except Exception as exc:
        logger.exception("Voice quality check failed for %s", voice_id)
        data = {
            "quality_status": "error",
            "error": str(exc)[:200],
            "sample_duration_sec": sample_duration_sec(sample),
            "sample_bytes": sample.stat().st_size,
        }
        save_quality(voice_id, data)
        return {**sample_stats(voice_id), **data}
