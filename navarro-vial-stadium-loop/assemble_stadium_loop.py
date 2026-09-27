#!/usr/bin/env python3
"""Build stadium loop from PNG sequence with crossfade (no GPU)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEQ_PATH = ROOT / "sequence.json"
VF = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    if not SEQ_PATH.is_file():
        sys.exit(f"Missing {SEQ_PATH}")

    seq = json.loads(SEQ_PATH.read_text(encoding="utf-8"))
    frames = seq["uniqueFrames"]
    order = seq["playbackOrder"]
    forward = float(os.environ.get("FORWARD_SEC", seq.get("forwardSeconds", 6)))
    reverse = float(os.environ.get("REVERSE_SEC", seq.get("reverseSeconds", 6)))
    total = forward + reverse
    fade = float(os.environ.get("FADE_SEC", "0.45"))
    fps = int(os.environ.get("FPS", "30"))
    out_dir = Path(os.environ.get("OUT_DIR", ROOT / "export"))
    out_dir.mkdir(parents=True, exist_ok=True)

    n = len(order)
    seg_dur = (total + (n - 1) * fade) / n

    tmp = Path(tempfile.mkdtemp(prefix="stadium-loop-"))
    segments: list[Path] = []

    try:
        for i, idx in enumerate(order):
            img = ROOT / frames[idx - 1]
            if not img.is_file():
                sys.exit(f"Missing frame: {img}")
            seg = tmp / f"seg_{i:02d}.mp4"
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-framerate",
                    str(fps),
                    "-t",
                    f"{seg_dur:.4f}",
                    "-i",
                    str(img),
                    "-vf",
                    VF,
                    "-an",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg),
                ]
            )
            segments.append(seg)

        current = segments[0]
        acc = seg_dur
        for i in range(1, len(segments)):
            nxt = segments[i]
            out = tmp / f"merge_{i:02d}.mp4"
            offset = max(0.0, acc - fade)
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(current),
                    "-i",
                    str(nxt),
                    "-filter_complex",
                    f"[0:v][1:v]xfade=transition=fade:duration={fade}:offset={offset:.4f}[v]",
                    "-map",
                    "[v]",
                    "-an",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(out),
                ]
            )
            current = out
            acc = acc + seg_dur - fade

        master = out_dir / "hero-navarro-vial-stadium-loop.mp4"
        shutil.copy2(current, master)

        web_crf = os.environ.get("WEB_CRF", "23")
        web = out_dir / "hero-navarro-vial-stadium-loop-web.mp4"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(master),
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                web_crf,
                "-preset",
                "medium",
                "-maxrate",
                "6M",
                "-bufsize",
                "12M",
                str(web),
            ]
        )

        poster = out_dir / "poster-stadium-loop.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(web),
                "-vf",
                "select=eq(n\\,0)",
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(poster),
            ]
        )

        # Poster from peak frame (completed stadium)
        peak = out_dir / "poster-stadium-complete.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(ROOT / frames[7]),
                "-vf",
                VF,
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(peak),
            ]
        )

        print(f"Master: {master} ({master.stat().st_size // 1024} KB)")
        print(f"Web:    {web} ({web.stat().st_size // 1024} KB)")
        print(f"Poster: {poster}")
        print(f"Peak:   {peak}")
        print(f"Duration target: {total}s | fade: {fade}s | segments: {n}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
