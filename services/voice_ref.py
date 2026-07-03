"""Prepare reference audio for XTTS (short clip works best)."""

import logging
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

XTTS_REF_SECONDS = 10.0


def prepare_xtts_reference(ref: Path) -> Path:
    """Return a ~10s mono clip cached beside the voice sample."""
    if not ref.is_file():
        raise FileNotFoundError(f"reference missing: {ref}")
    cache = ref.parent / "reference_xtts10s.wav"
    if cache.exists() and cache.stat().st_mtime >= ref.stat().st_mtime:
        return cache

    with wave.open(str(ref), "rb") as src:
        channels = src.getnchannels()
        width = src.getsampwidth()
        rate = src.getframerate()
        max_frames = int(rate * XTTS_REF_SECONDS)
        frames = src.readframes(max_frames)

    cache.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(cache), "wb") as dst:
        dst.setnchannels(channels)
        dst.setsampwidth(width)
        dst.setframerate(rate)
        dst.writeframes(frames)
    logger.info("XTTS reference clip: %s (%.1fs from %s)", cache.name, XTTS_REF_SECONDS, ref.name)
    return cache
