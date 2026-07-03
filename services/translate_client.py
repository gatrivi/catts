"""Offline EN↔ES translation via Argos in .venv subprocess."""

import json
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

SCRIPT = BASE_DIR / "scripts" / "translate_text.py"
_PAIRS = {("en", "es"), ("es", "en")}


def _site_packages() -> Path | None:
    if not VENV_PY.is_file():
        return None
    root = VENV_PY.parent.parent
    sp = root / "Lib" / "site-packages"
    if sp.is_dir():
        return sp
    sp = root / f"lib/python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    return sp if sp.is_dir() else None


def available() -> bool:
    sp = _site_packages()
    if not sp or not (sp / "argostranslate").is_dir():
        return False
    # language packs live under .../argostranslate/package/...
    pkg_dir = sp / "argostranslate" / "package"
    return pkg_dir.is_dir() and any(pkg_dir.iterdir())


def translate(text: str, from_lang: str, to_lang: str) -> str:
    from_lang = from_lang[:2].lower()
    to_lang = to_lang[:2].lower()
    if from_lang == to_lang:
        return text
    if (from_lang, to_lang) not in _PAIRS:
        raise ValueError("Only English ↔ Spanish supported")
    if not VENV_PY.is_file() or not SCRIPT.is_file():
        raise RuntimeError("Translation not installed — run scripts/setup_stt.ps1")
    proc = subprocess.run(
        [str(VENV_PY), str(SCRIPT), "--text", text, "--from", from_lang, "--to", to_lang],
        capture_output=True,
        text=True,
        timeout=120,
    )
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    try:
        resp = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError((proc.stderr or proc.stdout or "translate failed")[-500:]) from exc
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error") or "translate failed")
    return resp["text"]
