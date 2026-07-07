"""Offline EN↔ES translation via Argos in .venv subprocess."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR, DATA_DIR

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    VENV_PY = BASE_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = BASE_DIR / ".venv" / "bin" / "python"

SCRIPT = BASE_DIR / "scripts" / "translate_text.py"
_PAIRS = {("en", "es"), ("es", "en")}


def _argos_env() -> dict[str, str]:
    argos_home = DATA_DIR / "argos_runtime"
    config_home = argos_home / "config"
    data_home = argos_home / "data"
    cache_home = argos_home / "cache"
    for path in (config_home, data_home, cache_home):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("XDG_CONFIG_HOME", str(config_home))
    env.setdefault("XDG_DATA_HOME", str(data_home))
    env.setdefault("XDG_CACHE_HOME", str(cache_home))
    env.setdefault("ARGOS_CHUNK_TYPE", "ARGOSTRANSLATE")
    env.setdefault("ARGOS_STANZA_AVAILABLE", "false")
    return env


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
    if not sp or not SCRIPT.is_file():
        return False
    return (sp / "argostranslate").is_dir() and (sp / "ctranslate2").is_dir()


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
        env=_argos_env(),
    )
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    try:
        resp = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError((proc.stderr or proc.stdout or "translate failed")[-500:]) from exc
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error") or "translate failed")
    return resp["text"]
