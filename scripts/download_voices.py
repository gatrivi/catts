#!/usr/bin/env python3
"""Download Piper voice models for CatIntAssist TTS."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("TTS_MODELS_DIR", ROOT / "models"))

VOICES = [
    os.environ.get("TTS_VOICE_EN", "en_US-lessac-medium"),
    os.environ.get("TTS_VOICE_ES", "es_MX-ald-medium"),
]


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading voices to {MODELS_DIR}")

    for voice in VOICES:
        print(f"\n→ {voice}")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piper.download_voices",
                "--download-dir",
                str(MODELS_DIR),
                voice,
            ],
            check=True,
        )

    print("\nDone. Files:")
    for path in sorted(MODELS_DIR.glob("*.onnx*")):
        print(f"  {path.name} ({path.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
