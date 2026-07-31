"""Offline EN↔ES translation via Argos or Madlad in .venv."""

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from config import (
    BASE_DIR,
    DATA_DIR,
    TRANSLATE_ENGINE,
    MADLAD_MODEL_DIR,
    MADLAD_DEVICE,
    MADLAD_NUM_BEAMS,
    MADLAD_MAX_NEW_TOKENS,
    MADLAD_SPLIT_SENTENCES,
)

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    VENV_PY = BASE_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = BASE_DIR / ".venv" / "bin" / "python"

ARGOS_SCRIPT = BASE_DIR / "scripts" / "translate_text.py"
MADLAD_SCRIPT = BASE_DIR / "scripts" / "translate_madlad_worker.py"

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


def _madlad_model_ready() -> bool:
    # Offline translation requires the model to be saved locally.
    # We do a conservative check so we don't claim readiness without weights.
    if not MADLAD_MODEL_DIR.is_dir():
        return False
    has_config = (MADLAD_MODEL_DIR / "config.json").is_file()

    # Madlad uses SentencePiece; the common file name is `spiece.model`.
    has_tokenizer = any(
        (MADLAD_MODEL_DIR / name).is_file()
        for name in (
            "tokenizer.json",
            "tokenizer.model",
            "spiece.model",
            "sentencepiece.bpe.model",
        )
    )

    # Either safetensors or pytorch weights (names vary by export).
    has_weights = any(p.is_file() and p.name.endswith((".safetensors", ".bin")) for p in MADLAD_MODEL_DIR.iterdir())
    return has_config and has_tokenizer and has_weights


def _venv_has_modules(mods: tuple[str, ...]) -> bool:
    sp = _site_packages()
    if not sp:
        return False
    for m in mods:
        # Packages are directories for most modules (transformers/sentencepiece/etc).
        if not (sp / m).exists():
            return False
    return True


def available() -> bool:
    engine = TRANSLATE_ENGINE
    if engine == "auto":
        engine = "madlad" if _madlad_model_ready() else "argos"

    if engine == "madlad":
        if not VENV_PY.is_file() or not MADLAD_SCRIPT.is_file():
            return False
        if not _venv_has_modules(("transformers", "sentencepiece")):
            return False
        return _madlad_model_ready()

    # Default: Argos
    sp = _site_packages()
    if not sp or not ARGOS_SCRIPT.is_file():
        return False
    return (sp / "argostranslate").is_dir() and (sp / "ctranslate2").is_dir()


_madlad_proc: subprocess.Popen | None = None
_madlad_lock = threading.Lock()


def _start_madlad_worker() -> subprocess.Popen:
    global _madlad_proc
    if _madlad_proc and _madlad_proc.poll() is None:
        return _madlad_proc
    if not VENV_PY.is_file() or not MADLAD_SCRIPT.is_file():
        raise RuntimeError("Madlad translation not installed — run scripts/setup_madlad_model.py")
    if not _venv_has_modules(("transformers", "sentencepiece")):
        raise RuntimeError("Madlad translation requires `transformers` + `sentencepiece` in .venv")
    if not _madlad_model_ready():
        raise RuntimeError(
            f"Madlad model not ready — set CATTS_MADLAD_MODEL_DIR to an offline model folder:\n  {str(MADLAD_MODEL_DIR)}"
        )

    logger.info("Starting Madlad worker (model_dir=%s)…", MADLAD_MODEL_DIR)
    proc = subprocess.Popen(
        [
            str(VENV_PY),
            str(MADLAD_SCRIPT),
            str(MADLAD_MODEL_DIR),
            MADLAD_DEVICE,
            str(MADLAD_NUM_BEAMS),
            str(MADLAD_MAX_NEW_TOKENS),
            "1" if MADLAD_SPLIT_SENTENCES else "0",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    for _ in range(600):
        if proc.poll() is not None:
            # Read stderr last chunk to show why.
            msg = (proc.stderr.read() or "")[-800:]
            raise RuntimeError(msg or "Madlad worker exited")
        line = proc.stderr.readline()
        if not line:
            continue
        if "ready" in line.lower():
            _madlad_proc = proc
            return proc
    raise RuntimeError("Madlad worker timed out loading model")


def translate(text: str, from_lang: str, to_lang: str) -> str:
    from_lang = from_lang[:2].lower()
    to_lang = to_lang[:2].lower()
    if from_lang == to_lang:
        return text
    if (from_lang, to_lang) not in _PAIRS:
        raise ValueError("Only English ↔ Spanish supported")

    engine = TRANSLATE_ENGINE
    if engine == "auto":
        engine = "madlad" if _madlad_model_ready() else "argos"

    if engine == "madlad":
        with _madlad_lock:
            proc = _start_madlad_worker()
            assert proc.stdin and proc.stdout
            proc.stdin.write(
                json.dumps({"cmd": "translate", "text": text, "from_lang": from_lang, "to_lang": to_lang}) + "\n"
            )
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("Madlad worker closed")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError((line or "madlad translate failed")[-500:]) from exc
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "madlad translate failed")
        return resp["text"]

    # Argos (default)
    if not VENV_PY.is_file() or not ARGOS_SCRIPT.is_file():
        raise RuntimeError("Translation not installed — run scripts/setup_stt.ps1")
    proc = subprocess.run(
        [str(VENV_PY), str(ARGOS_SCRIPT), "--text", text, "--from", from_lang, "--to", to_lang],
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
