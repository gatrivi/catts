"""Check whether the current Python environment can run CATTS."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "catts.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_MODULES = [
    "fastapi",
    "uvicorn",
    "multipart",
    "httpx",
    "aiofiles",
]

BOOK_MODULES = [
    "fitz",
    "ebooklib",
    "docx",
    "langdetect",
]

VOICE_MODULES = [
    "TTS",
    "torch",
    "torchaudio",
]

STT_TRANSLATE_MODULES = [
    "faster_whisper",
    "argostranslate",
]


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def module_report(names: list[str]) -> dict[str, bool]:
    return {name: has_module(name) for name in names}


def status(values: dict[str, bool]) -> str:
    if all(values.values()):
        return "PASS"
    if any(values.values()):
        return "PARTIAL"
    return "FAIL"


def xtts_cache_status() -> dict:
    candidates = [
        ROOT / "data" / "local_appdata" / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2",
        Path.home() / "AppData" / "Local" / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2",
    ]
    cache = next((path for path in candidates if path.exists()), candidates[0])
    if not cache.exists():
        return {"status": "FAIL", "path": str(cache), "files": 0, "bytes": 0}
    files = [p for p in cache.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return {
        "status": "PASS" if total > 100_000_000 else "PARTIAL",
        "path": str(cache),
        "files": len(files),
        "bytes": total,
    }


def xtts_terms_status() -> dict:
    accepted = os.getenv("CATTS_ACCEPT_COQUI_CPML", "").lower() in {"1", "true", "yes"}
    return {
        "status": "PASS" if accepted else "FAIL",
        "accepted": accepted,
        "env": "CATTS_ACCEPT_COQUI_CPML",
    }


def whisper_cache_status() -> dict:
    cache = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-small" / "blobs"
    if not cache.exists():
        return {"status": "FAIL", "path": str(cache), "files": 0, "bytes": 0}
    files = [p for p in cache.iterdir() if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return {
        "status": "PASS" if total > 100_000_000 else "PARTIAL",
        "path": str(cache),
        "files": len(files),
        "bytes": total,
    }


def voices_status() -> dict:
    voices_dir = DATA_DIR / "voices"
    if not voices_dir.exists():
        return {"status": "FAIL", "voices": 0, "usable": 0}
    voice_dirs = [p for p in voices_dir.iterdir() if p.is_dir()]
    usable = 0
    for voice_dir in voice_dirs:
        sample = voice_dir / "sample.wav"
        reference = voice_dir / "reference.wav"
        if sample.exists() and reference.exists() and sample.stat().st_size > 100_000 and reference.stat().st_size > 100_000:
            usable += 1
    return {
        "status": "PASS" if usable else ("PARTIAL" if voice_dirs else "FAIL"),
        "voices": len(voice_dirs),
        "usable": usable,
    }


def db_status() -> dict:
    if not DB_PATH.exists():
        return {"status": "FAIL", "path": str(DB_PATH), "voices": 0, "jobs": 0}
    with sqlite3.connect(DB_PATH) as conn:
        voices = conn.execute("select count(*) from voices").fetchone()[0]
        jobs = conn.execute("select count(*) from jobs").fetchone()[0]
    return {"status": "PASS", "path": str(DB_PATH), "voices": voices, "jobs": jobs}


def _ffmpeg_status() -> dict:
    try:
        from services.ffmpeg_util import ffmpeg_path

        path = ffmpeg_path()
    except Exception:
        path = None
    return {"status": "PASS" if path else "FAIL", "path": path}


def main() -> int:
    api = module_report(API_MODULES)
    books = module_report(BOOK_MODULES)
    voice = module_report(VOICE_MODULES)
    stt_translate = module_report(STT_TRANSLATE_MODULES)

    report = {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "is_repo_venv": Path(sys.prefix).name == ".venv" or str(ROOT / ".venv").lower() in sys.executable.lower(),
        "api_modules": {"status": status(api), "modules": api},
        "book_modules": {"status": status(books), "modules": books},
        "voice_modules": {"status": status(voice), "modules": voice},
        "stt_translate_modules": {"status": status(stt_translate), "modules": stt_translate},
        "ffmpeg": _ffmpeg_status(),
        "ocr": {
            "status": "PASS" if os.getenv("CATTS_WORKER_URL") else "FAIL",
            "worker_url": os.getenv("CATTS_WORKER_URL") or "",
            "ocr_engine": os.getenv("CATTS_OCR_ENGINE", "none"),
        },
        "xtts_terms": xtts_terms_status(),
        "xtts_cache": xtts_cache_status(),
        "whisper_cache": whisper_cache_status(),
        "voices": voices_status(),
        "database": db_status(),
    }

    print(json.dumps(report, indent=2))
    hard_fail = any(
        section["status"] == "FAIL"
        for section in [
            report["api_modules"],
            report["book_modules"],
            report["voice_modules"],
            report["stt_translate_modules"],
        ]
    )
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
