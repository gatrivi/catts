"""Prepare reference audio for XTTS (energy-picked clips, not just first 10s)."""

from __future__ import annotations

import logging
import math
import subprocess
import wave
from array import array
from pathlib import Path

from services.ffmpeg_util import ffmpeg_path

logger = logging.getLogger(__name__)

# XTTS clones best from several clean mid-length clips, not one truncated head.
XTTS_CLIP_SECONDS = 12.0
XTTS_NUM_CLIPS = 3
XTTS_MAX_REF_SECONDS = 45.0  # don't scan forever on huge files


def _read_wav_mono_pcm16(path: Path) -> tuple[array, int]:
    with wave.open(str(path), "rb") as src:
        channels = src.getnchannels()
        width = src.getsampwidth()
        rate = src.getframerate()
        nframes = src.getnframes()
        max_frames = min(nframes, int(rate * XTTS_MAX_REF_SECONDS))
        raw = src.readframes(max_frames)
    if width != 2:
        # Fallback: rewrite via wave only supports what we write; convert crudely.
        raise ValueError(f"expected 16-bit PCM wav, got sampwidth={width} for {path}")
    samples = array("h")
    samples.frombytes(raw)
    if channels > 1:
        mono = array("h")
        for i in range(0, len(samples), channels):
            chunk = samples[i : i + channels]
            mono.append(int(sum(chunk) / len(chunk)))
        samples = mono
    return samples, rate


def _write_wav_mono_pcm16(path: Path, samples: array, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(rate)
        dst.writeframes(samples.tobytes())


def _rms(chunk: array) -> float:
    if not chunk:
        return 0.0
    acc = 0.0
    for s in chunk:
        acc += float(s) * float(s)
    return math.sqrt(acc / len(chunk))


def _pick_energy_windows(samples: array, rate: int, clip_sec: float, n_clips: int) -> list[array]:
    """Pick non-overlapping windows with highest RMS (skip leading silence)."""
    win = int(rate * clip_sec)
    if len(samples) <= win:
        return [samples]

    hop = max(win // 4, rate // 2)  # 0.5s–3s hop
    scored: list[tuple[float, int]] = []
    for start in range(0, len(samples) - win + 1, hop):
        # Prefer not the very first 1.5s (often breath/noise/WhatsApp beep).
        if start < int(rate * 1.5) and len(samples) > win * 2:
            continue
        scored.append((_rms(samples[start : start + win]), start))
    scored.sort(reverse=True, key=lambda x: x[0])

    picked: list[array] = []
    used: list[tuple[int, int]] = []
    for _rms_v, start in scored:
        end = start + win
        if any(not (end <= a or start >= b) for a, b in used):
            continue
        picked.append(samples[start:end])
        used.append((start, end))
        if len(picked) >= n_clips:
            break
    if not picked:
        picked = [samples[:win]]
    return picked


def prepare_playable_wav(src: Path, dest: Path | None = None) -> Path:
    """Ensure a real PCM WAV (handles mislabeled OGG/MP3 saved as .wav)."""
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(src)
    out = Path(dest) if dest else src.with_name(src.stem + "_pcm.wav")
    try:
        with wave.open(str(src), "rb") as _:
            return src  # already RIFF wav
    except wave.Error:
        pass
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError(f"reference is not WAV and ffmpeg missing: {src}")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-ar", "24000", "-ac", "1", str(out)],
        check=True,
        capture_output=True,
    )
    return out


def prepare_xtts_reference(ref: Path) -> Path:
    """Return primary ~12s energy-picked clip (compat for single-path callers)."""
    ref = prepare_playable_wav(ref, ref.parent / f"{ref.stem}_pcm.wav")
    clips = prepare_xtts_reference_clips(ref)
    return clips[0]


def prepare_xtts_reference_clips(ref: Path) -> list[Path]:
    """Return several energy-picked clips for stronger LatAm / speaker cloning."""
    if not ref.is_file():
        raise FileNotFoundError(f"reference missing: {ref}")

    ref = prepare_playable_wav(ref, ref.parent / f"{ref.stem}_pcm.wav")

    cache_dir = ref.parent / "xtts_refs"
    stamp = ref.stat().st_mtime_ns
    marker = cache_dir / f".stamp_{stamp}"
    if cache_dir.is_dir() and marker.exists():
        existing = sorted(cache_dir.glob("clip_*.wav"))
        if existing:
            return existing

    # Rebuild cache
    if cache_dir.exists():
        for old in cache_dir.glob("*"):
            try:
                old.unlink()
            except OSError:
                pass
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)

    samples, rate = _read_wav_mono_pcm16(ref)
    windows = _pick_energy_windows(samples, rate, XTTS_CLIP_SECONDS, XTTS_NUM_CLIPS)
    out_paths: list[Path] = []
    for i, win in enumerate(windows, 1):
        path = cache_dir / f"clip_{i:02d}.wav"
        _write_wav_mono_pcm16(path, win, rate)
        out_paths.append(path)
        logger.info(
            "XTTS ref clip %s: %.1fs rms=%.0f from %s",
            path.name,
            len(win) / rate,
            _rms(win),
            ref.name,
        )

    # Also keep legacy single-file cache for older callers
    legacy = ref.parent / "reference_xtts10s.wav"
    _write_wav_mono_pcm16(legacy, windows[0], rate)

    marker.write_text(str(stamp), encoding="utf-8")
    return out_paths
