"""
Audio silence checks used by diagnostics and smoke tests.

Objetivo: detectar casos donde el stack “devuelve audio” pero en realidad
es silencioso (placeholder).
"""

from __future__ import annotations

import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from services.ffmpeg_util import ffmpeg_path


def peak_from_wav_int16(wav_path: Path) -> float:
    """Max absolute amplitude normalized to [0..1] for 16-bit PCM WAV."""
    with wave.open(str(wav_path), "rb") as wf:
        sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            return 0.0
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    if not raw:
        return 0.0

    cnt = len(raw) // 2
    max_abs = 0
    for i in range(cnt):
        v = struct.unpack_from("<h", raw, i * 2)[0]
        a = abs(v)
        if a > max_abs:
            max_abs = a

    return max_abs / 32768.0


def to_wav_if_needed(audio_path: Path) -> Path | None:
    """Convert audio to WAV via ffmpeg if needed; returns WAV path or None."""
    if audio_path.suffix.lower() == ".wav":
        return audio_path
    ffmpeg = ffmpeg_path()
    if not ffmpeg or not audio_path.exists():
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="catts_silence_"))
    out = tmp_dir / (audio_path.stem + ".wav")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(out)],
        check=True,
        capture_output=True,
    )
    return out


def is_not_silent(audio_path: Path, *, threshold_peak: float = 0.008) -> tuple[bool, float]:
    """
    Returns (ok, peak).
    If we cannot verify (no ffmpeg / decode error), we return ok=True.
    """
    wav_path = to_wav_if_needed(audio_path)
    if wav_path is None:
        return True, 0.0
    try:
        peak = peak_from_wav_int16(wav_path)
    except Exception:
        return True, 0.0
    return peak >= threshold_peak, peak

