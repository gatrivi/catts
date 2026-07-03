"""Remove bulky intermediate audio files after audiobook packaging."""

import logging
from pathlib import Path

from config import KEEP_INTERMEDIATE_AUDIO

logger = logging.getLogger(__name__)


def cleanup_job_artifacts(job_dir: Path, force: bool = False) -> dict:
    """Drop per-chunk WAVs and other temp files; keep final outputs."""
    if KEEP_INTERMEDIATE_AUDIO and not force:
        return {"skipped": True, "removed": 0, "freed_bytes": 0}

    removed = 0
    freed = 0
    audio = job_dir / "audio"

    patterns = [
        audio.glob("chapter_*_part_*.*") if audio.exists() else [],
        audio.glob("chapter_*.wav") if audio.exists() else [],
        [job_dir / "combined.wav"],
        [job_dir / "ffmetadata.txt"],
        [job_dir / "concat_list.txt"],
    ]
    for group in patterns:
        for path in group:
            if path.exists() and path.is_file():
                freed += path.stat().st_size
                path.unlink()
                removed += 1

    logger.info("Cleaned %s files (%d bytes) from %s", removed, freed, job_dir.name)
    return {"removed": removed, "freed_bytes": freed}
