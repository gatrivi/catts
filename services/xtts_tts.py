"""Coqui XTTS v2 via project .venv subprocess (CPU / AMD friendly)."""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    VENV_PY = BASE_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = BASE_DIR / ".venv" / "bin" / "python"

SCRIPT = BASE_DIR / "scripts" / "xtts_synth.py"


def _site_packages() -> Path | None:
    if not VENV_PY.is_file():
        return None
    root = VENV_PY.parent.parent
    for rel in ("Lib/site-packages", f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"):
        sp = root / rel.replace("/", "\\") if sys.platform == "win32" else root / rel
        if sp.is_dir():
            return sp
    return None


def available() -> bool:
    sp = _site_packages()
    return bool(sp and (sp / "TTS").is_dir() and SCRIPT.is_file())


def _run_sync(text: str, ref_audio: Path, output_path: Path, lang: str) -> None:
    cmd = [
        str(VENV_PY),
        str(SCRIPT),
        "--text",
        text,
        "--ref",
        str(ref_audio),
        "--out",
        str(output_path),
        "--lang",
        lang,
    ]
    logger.info("XTTS synth (%d chars) -> %s", len(text), output_path.name)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "xtts failed").strip()[-800:]
        raise RuntimeError(err)


async def synthesize(
    text: str,
    output_path: Path,
    ref_audio: Path | None = None,
    lang: str = "en",
) -> Path:
    if not available():
        raise RuntimeError("XTTS not ready — run scripts/setup_xtts.ps1")
    if not ref_audio or not ref_audio.is_file():
        raise ValueError("reference audio required for voice clone")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_sync, text, ref_audio, output_path, lang)
    return output_path
