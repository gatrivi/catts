"""Local STT via faster-whisper persistent worker in .venv."""

import asyncio
import base64
import json
import logging
import subprocess
import sys
import threading
from pathlib import Path

from config import BASE_DIR, STT_MODEL

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    VENV_PY = BASE_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PY = BASE_DIR / ".venv" / "bin" / "python"

WORKER_SCRIPT = BASE_DIR / "scripts" / "stt_worker.py"

_worker_proc: subprocess.Popen | None = None
_worker_lock = threading.Lock()


def available() -> bool:
    if not VENV_PY.is_file() or not WORKER_SCRIPT.is_file():
        return False
    sp = VENV_PY.parent.parent / "Lib" / "site-packages"
    if sys.platform != "win32":
        sp = VENV_PY.parent.parent / f"lib/python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    return (sp / "faster_whisper").is_dir()


def _start_worker() -> subprocess.Popen:
    global _worker_proc
    if _worker_proc and _worker_proc.poll() is None:
        return _worker_proc
    logger.info("Starting STT worker (model=%s)", STT_MODEL)
    proc = subprocess.Popen(
        [str(VENV_PY), str(WORKER_SCRIPT), STT_MODEL],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    for _ in range(600):
        if proc.poll() is not None:
            raise RuntimeError((proc.stderr.read() or "")[-500:])
        line = proc.stderr.readline()
        if "ready" in line.lower():
            _worker_proc = proc
            logger.info("STT worker ready")
            return proc
    raise RuntimeError("STT worker timed out loading model")


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
        logger.warning("STT warmup failed: %s", exc)


def _transcribe_sync(audio_path: Path, lang: str | None) -> dict:
    with _worker_lock:
        proc = _start_worker()
        req = json.dumps({"audio_path": str(audio_path), "lang": lang or "auto"})
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("STT worker closed")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "stt failed")
        return resp


async def transcribe_file(audio_path: Path, lang: str | None = None) -> dict:
    if not available():
        raise RuntimeError("STT not installed — run scripts/setup_stt.ps1")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, audio_path, lang)
