"""Fish Speech (ZLUDA/AMD) HTTP client — POST /v1/tts on a local api_server.

Critical: every chunk MUST use the same reference wav. Empty references →
Fish samples a random speaker each call (accents flip mid-book). Never allow that.
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import httpx

from config import (
    DATA_DIR,
    DEFAULT_VOICE_ID,
    FISH_REFERENCE_ID,
    FISH_REFERENCE_ID_ES,
    FISH_URL,
    TTS_SPEED,
    VOICES_DIR,
)
from services.ffmpeg_util import change_tempo

logger = logging.getLogger(__name__)

# Fixed seed helps sampling; timbre lock still comes from the same ref file.
FISH_SEED = int(os.getenv("CATTS_FISH_SEED", "42"))
FISH_TEMPERATURE = float(os.getenv("CATTS_FISH_TEMPERATURE", "0.5"))

# Prefer these names (EN first for audiobook focus).
_FISH_REF_NAMES_EN = (
    "fish_ref_en_15s.wav",
    "fish_ref_15s.wav",
    "fish_ref.wav",
    "reference.wav",
    "sample.wav",
    "chatterbox_ref.wav",
)
_FISH_REF_NAMES_ES = (
    "fish_ref_es_15s.wav",
    "fish_ref_15s.wav",
    "fish_ref.wav",
    "reference.wav",
    "sample.wav",
    "chatterbox_ref.wav",
)


def configured() -> bool:
    return bool(FISH_URL)


async def ready() -> bool:
    if not configured():
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{FISH_URL}/v1/health")
        return response.status_code < 500
    except Exception:
        return False


def status_message(is_ready: bool) -> str:
    if is_ready:
        return f"Fish Speech ready at {FISH_URL}"
    return f"Fish Speech not reachable at {FISH_URL} — run scripts\\start_fish_zluda.ps1"


def _lang_key(lang: str | None) -> str:
    return "es" if (lang or "en").lower().startswith("es") else "en"


def _voice_dir(voice_id: str | None) -> Path | None:
    if not voice_id:
        return None
    p = VOICES_DIR / voice_id
    return p if p.is_dir() else None


def _first_existing(dir_path: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        cand = dir_path / name
        if cand.is_file() and cand.stat().st_size > 1000:
            return cand
    # any fish_ref*.wav
    hits = sorted(dir_path.glob("fish_ref*.wav"))
    for h in hits:
        if h.is_file() and h.stat().st_size > 1000:
            return h
    return None


def resolve_fish_ref(
    *,
    lang: str = "en",
    voice_id: str | None = None,
    ref_audio: Path | None = None,
) -> Path:
    """One stable wav for the whole book. Raises if missing (never silent-random)."""
    if ref_audio and Path(ref_audio).is_file():
        return Path(ref_audio)

    key = _lang_key(lang)
    names = _FISH_REF_NAMES_ES if key == "es" else _FISH_REF_NAMES_EN

    # Env absolute paths (optional override)
    env_path = os.getenv("CATTS_FISH_REF_ES" if key == "es" else "CATTS_FISH_REF_EN", "").strip()
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    # Preferred voice id (job → default → common folder names)
    candidates_ids: list[str] = []
    if voice_id:
        candidates_ids.append(voice_id)
    if DEFAULT_VOICE_ID and DEFAULT_VOICE_ID not in candidates_ids:
        candidates_ids.append(DEFAULT_VOICE_ID)
    for guess in ("gaston-en", "gaston-esp", "gaston", "0b0ad49fcac94af4"):
        if guess not in candidates_ids:
            candidates_ids.append(guess)

    for vid in candidates_ids:
        vdir = _voice_dir(vid)
        if not vdir:
            continue
        hit = _first_existing(vdir, names)
        if hit:
            logger.info("Fish voice lock: %s (voice=%s lang=%s)", hit.name, vid, key)
            return hit

    # Last resort: scan voices/*/fish_ref*
    if VOICES_DIR.is_dir():
        for vdir in sorted(VOICES_DIR.iterdir()):
            if not vdir.is_dir():
                continue
            hit = _first_existing(vdir, names)
            if hit:
                logger.info("Fish voice lock (scan): %s", hit)
                return hit

    # Static demo refs from Our Fathers bake
    static_fish = DATA_DIR.parent / "static" / "fish"
    for name in names:
        hit = static_fish / name
        if hit.is_file():
            return hit

    raise RuntimeError(
        "Fish needs one locked reference wav (same file every chunk). "
        "Save e.g. data/voices/<id>/fish_ref_en_15s.wav (10–30s clean EN), "
        "set CATTS_DEFAULT_VOICE_ID, or CATTS_FISH_REF_EN=/path/to/ref.wav. "
        "Without a ref Fish randomly changes speaker each chunk — unusable for books."
    )


def _reference_id_for_lang(lang: str) -> str | None:
    key = _lang_key(lang)
    if key == "es":
        return FISH_REFERENCE_ID_ES or FISH_REFERENCE_ID
    return FISH_REFERENCE_ID


@lru_cache(maxsize=8)
def _cached_ref_b64(path_str: str, mtime_ns: int, size: int) -> str:
    # ponytail: cache base64 so 200 chunks don't re-encode the same 15s wav
    return base64.b64encode(Path(path_str).read_bytes()).decode("ascii")


def _ref_text_beside(ref: Path) -> str:
    for name in (f"{ref.stem}.txt", "fish_ref_text.txt", "reference.txt", "prompt.txt"):
        p = ref.parent / name
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore").strip()[:500]
    return ""


def _max_new_tokens(text: str) -> int:
    # ~4 chars/token rough; keep headroom but don't always burn 1024
    n = max(128, min(1024, int(len(text) * 1.2) + 64))
    return n


def _payload(
    text: str,
    ref_audio: Path | None = None,
    ref_text: str = "",
    *,
    lang: str = "en",
    require_ref: bool = False,
) -> dict:
    references = []
    reference_id = _reference_id_for_lang(lang)
    if ref_audio and Path(ref_audio).is_file():
        st = Path(ref_audio).stat()
        references.append(
            {
                "audio": _cached_ref_b64(str(Path(ref_audio).resolve()), st.st_mtime_ns, st.st_size),
                "text": ref_text or _ref_text_beside(Path(ref_audio)),
            }
        )
        reference_id = None  # file refs win over server reference_id
    elif require_ref and not reference_id:
        raise RuntimeError("Fish payload built without reference — refusing random voice")

    return {
        "text": text,
        "format": "wav",
        "references": references,
        "reference_id": reference_id,
        "normalize": True,
        "streaming": False,
        "chunk_length": 200,
        "max_new_tokens": _max_new_tokens(text),
        "top_p": 0.7,
        "repetition_penalty": 1.2,
        "temperature": FISH_TEMPERATURE,
        "seed": FISH_SEED,
        "use_memory_cache": "on" if references or reference_id else "off",
    }


def _apply_speed(wav_bytes: bytes, output_path: Path | None = None) -> bytes:
    """Fish 1.5 API has no speed field — stretch with ffmpeg atempo when needed."""
    if abs(TTS_SPEED - 1.0) < 1e-3:
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)
        return wav_bytes

    with tempfile.TemporaryDirectory(prefix="catts_fish_speed_") as td:
        raw = Path(td) / "raw.wav"
        out = Path(td) / "slow.wav"
        raw.write_bytes(wav_bytes)
        change_tempo(raw, out, TTS_SPEED)
        data = out.read_bytes()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    return data


async def synthesize(
    text: str,
    output_path: Path,
    ref_audio: Path | None = None,
    ref_text: str = "",
    *,
    lang: str = "en",
    voice_id: str | None = None,
) -> Path:
    if not configured():
        raise RuntimeError("Fish Speech not configured — set CATTS_FISH_URL")

    locked = resolve_fish_ref(lang=lang, voice_id=voice_id, ref_audio=ref_audio)
    payload = _payload(text, ref_audio=locked, ref_text=ref_text, lang=lang, require_ref=True)
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{FISH_URL}/v1/tts",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    _apply_speed(response.content, output_path)
    return output_path


async def live_tts(
    text: str,
    ref_audio: Path | None = None,
    ref_text: str = "",
    *,
    lang: str = "en",
    voice_id: str | None = None,
) -> tuple[bytes, str]:
    if not configured():
        raise RuntimeError("Fish Speech not configured — set CATTS_FISH_URL")

    locked = resolve_fish_ref(lang=lang, voice_id=voice_id, ref_audio=ref_audio)
    payload = _payload(text, ref_audio=locked, ref_text=ref_text, lang=lang, require_ref=True)
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{FISH_URL}/v1/tts",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
    return _apply_speed(response.content), "fish"
