"""Coqui XTTS v2 via persistent .venv worker (model loaded once)."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from config import BASE_DIR
from services.voice_ref import prepare_xtts_reference

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    VENV_PY = BASE_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = BASE_DIR / ".venv" / "bin" / "python"

WORKER_SCRIPT = BASE_DIR / "scripts" / "xtts_worker.py"
SCRIPT = BASE_DIR / "scripts" / "xtts_synth.py"  # fallback

_worker_proc: subprocess.Popen | None = None
_worker_lock = threading.Lock()


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
    return bool(sp and (sp / "TTS").is_dir() and WORKER_SCRIPT.is_file())


def worker_status() -> dict:
    """UI-facing readiness (installed vs model hot)."""
    if not available():
        return {
            "installed": False,
            "ready": False,
            "message": "XTTS not installed — run scripts/setup_xtts.ps1",
        }
    if os.getenv("CATTS_ACCEPT_COQUI_CPML", "").lower() not in {"1", "true", "yes"}:
        return {
            "installed": True,
            "ready": False,
            "message": "XTTS installed - set CATTS_ACCEPT_COQUI_CPML=1 after accepting Coqui CPML/commercial terms",
        }
    if _worker_proc is not None and _worker_proc.poll() is None:
        return {
            "installed": True,
            "ready": True,
            "message": "XTTS ready (model loaded)",
        }
    return {
        "installed": True,
        "ready": False,
        "message": "XTTS installed — model loading (first start ~1 min) or idle",
    }


def _start_worker() -> subprocess.Popen:
    global _worker_proc
    if _worker_proc and _worker_proc.poll() is None:
        return _worker_proc
    logger.info("Starting XTTS worker (first start loads ~2GB model, then stays hot)")
    proc = subprocess.Popen(
        [str(VENV_PY), str(WORKER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    for _ in range(600):
        if proc.poll() is not None:
            err = (proc.stderr.read() or "")[-500:]
            raise RuntimeError(f"XTTS worker exited early: {err}")
        line = proc.stderr.readline()
        if "ready" in line.lower():
            _worker_proc = proc
            logger.info("XTTS worker ready")
            return proc
    raise RuntimeError("XTTS worker timed out while loading model")


def warmup_worker() -> None:
    if not available():
        return
    try:
        with _worker_lock:
            proc = _start_worker()
            proc.stdin.write(json.dumps({"cmd": "ping"}) + "\n")
            proc.stdin.flush()
            proc.stdout.readline()
    except Exception as exc:
        logger.warning("XTTS warmup failed: %s", exc)


def _synth_via_worker(text: str, ref_audio: Path, output_path: Path, lang: str) -> None:
    ref = prepare_xtts_reference(ref_audio)
    with _worker_lock:
        proc = _start_worker()
        req = json.dumps(
            {"text": text, "ref": str(ref), "out": str(output_path), "lang": lang},
        )
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("XTTS worker closed stdout")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "xtts failed")


def _synth_via_subprocess(text: str, ref_audio: Path, output_path: Path, lang: str) -> None:
    ref = prepare_xtts_reference(ref_audio)
    cmd = [
        str(VENV_PY), str(SCRIPT),
        "--text", text, "--ref", str(ref), "--out", str(output_path), "--lang", lang,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "xtts failed").strip()[-800:]
        raise RuntimeError(err)


def _run_sync(text: str, ref_audio: Path, output_path: Path, lang: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _synth_via_worker(text, ref_audio, output_path, lang)
    except Exception as exc:
        logger.warning("XTTS worker failed (%s), trying one-shot subprocess", exc)
        global _worker_proc
        _worker_proc = None
        _synth_via_subprocess(text, ref_audio, output_path, lang)


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
