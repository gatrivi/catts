"""Locate ffmpeg for audio conversion and packaging."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_path() -> str | None:
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def ffmpeg_available() -> bool:
    return ffmpeg_path() is not None


def change_tempo(src: Path, dst: Path, speed: float) -> Path:
    """Stretch/compress tempo without pitch shift. speed=0.9 ≈ 10% slower."""
    if abs(speed - 1.0) < 1e-3:
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        return dst
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        return dst
    # atempo only accepts 0.5–2.0; we already clamp TTS_SPEED to that.
    tempo = max(0.5, min(float(speed), 2.0))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst if src.resolve() != dst.resolve() else dst.with_suffix(".tempo_tmp.wav")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-filter:a", f"atempo={tempo}", "-ac", "1", str(tmp)],
        check=True,
        capture_output=True,
    )
    if tmp.resolve() != dst.resolve():
        tmp.replace(dst)
    return dst
