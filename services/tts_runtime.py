"""Runtime TTS engine override (no .env edit / restart needed)."""

from __future__ import annotations

import threading
from typing import Any

from config import FISH_URL, KOKORO_URL, TTS_ENGINE, WORKER_URL
from services import chatterbox_tts, fish_tts, kokoro_tts, melotts_tts, pocket_tts, xtts_tts

_lock = threading.Lock()
_override: str | None = None

KNOWN = ("fish", "kokoro", "melotts", "xtts", "pocket", "chatterbox", "gptsovits", "edge")


def get_engine() -> str:
    with _lock:
        return (_override or TTS_ENGINE or "edge").strip().lower()


def set_engine(name: str) -> str:
    key = (name or "").strip().lower()
    if key not in KNOWN:
        raise ValueError(f"Unknown engine '{name}'. Choose one of: {', '.join(KNOWN)}")
    with _lock:
        global _override
        previous = (_override or TTS_ENGINE or "edge").strip().lower()
        _override = key
    if key == "melotts" and previous != "melotts":
        threading.Thread(
            target=melotts_tts.warmup_worker,
            daemon=True,
            name="melotts-runtime-warmup",
        ).start()
    elif previous == "melotts" and key != "melotts":
        melotts_tts.shutdown_worker()
    return key


def clear_override() -> str:
    with _lock:
        global _override
        previous = (_override or TTS_ENGINE or "edge").strip().lower()
        _override = None
        active = (TTS_ENGINE or "edge").strip().lower()
    if active == "melotts" and previous != "melotts":
        threading.Thread(
            target=melotts_tts.warmup_worker,
            daemon=True,
            name="melotts-runtime-warmup",
        ).start()
    elif previous == "melotts" and active != "melotts":
        melotts_tts.shutdown_worker()
    return active


def _probe(name: str) -> dict[str, Any]:
    """Sync probe — readiness that needs await is filled by the route."""
    if name == "fish":
        return {
            "id": "fish",
            "label": "Fish Speech (ZLUDA)",
            "configured": fish_tts.configured(),
            "needs_server": True,
            "clone": True,
            "note": f"API {FISH_URL or '(unset)'}",
        }
    if name == "kokoro":
        return {
            "id": "kokoro",
            "label": "Kokoro (local EN/ES)",
            "configured": kokoro_tts.configured(),
            "needs_server": True,
            "clone": False,
            "note": f"API {KOKORO_URL}",
        }
    if name == "melotts":
        ok = melotts_tts.available()
        st = melotts_tts.worker_status()
        return {
            "id": "melotts",
            "label": "MeloTTS (local ES)",
            "configured": ok,
            "needs_server": False,
            "clone": False,
            "note": st.get("message") or ("installed" if ok else "not installed"),
            "ready_hint": bool(st.get("ready")),
        }
    if name == "xtts":
        st = xtts_tts.worker_status()
        return {
            "id": "xtts",
            "label": "XTTS v2",
            "configured": bool(st.get("installed")),
            "needs_server": False,
            "clone": True,
            "note": st.get("message") or "",
            "ready_hint": bool(st.get("ready")),
        }
    if name == "pocket":
        return {
            "id": "pocket",
            "label": "Pocket TTS",
            "configured": pocket_tts.available(),
            "needs_server": False,
            "clone": True,
            "note": pocket_tts.status_message() if pocket_tts.available() else "not installed",
        }
    if name == "chatterbox":
        ok = chatterbox_tts.available()
        return {
            "id": "chatterbox",
            "label": "Chatterbox",
            "configured": ok,
            "needs_server": False,
            "clone": True,
            "note": "pip: requirements-chatterbox.txt" if not ok else "installed (CPU OK)",
            "ready_hint": ok,
        }
    if name == "gptsovits":
        return {
            "id": "gptsovits",
            "label": "GPT-SoVITS",
            "configured": bool(WORKER_URL),
            "needs_server": True,
            "clone": True,
            "note": WORKER_URL or "set CATTS_WORKER_URL",
        }
    return {
        "id": "edge",
        "label": "Edge TTS",
        "configured": True,
        "needs_server": False,
        "clone": False,
        "note": "cloud Microsoft voices",
    }


def list_engines() -> list[dict[str, Any]]:
    active = get_engine()
    out = []
    for name in KNOWN:
        row = _probe(name)
        row["active"] = name == active
        out.append(row)
    return out
