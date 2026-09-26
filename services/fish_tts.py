"""Fish Speech (ZLUDA/AMD) HTTP client — POST /v1/tts on a local api_server."""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

import httpx

from config import FISH_URL, TTS_SPEED
from services.ffmpeg_util import change_tempo

logger = logging.getLogger(__name__)


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
    return f"Fish Speech not reachable at {FISH_URL} — run scripts\\start_fish_api.ps1"


def _payload(text: str, ref_audio: Path | None = None, ref_text: str = "") -> dict:
    references = []
    if ref_audio and ref_audio.is_file():
        references.append(
            {
                "audio": base64.b64encode(ref_audio.read_bytes()).decode("ascii"),
                "text": ref_text or "",
            }
        )
    return {
        "text": text,
        "format": "wav",
        "references": references,
        "reference_id": None,
        "normalize": True,
        "streaming": False,
        "chunk_length": 200,
        "max_new_tokens": 1024,
        "top_p": 0.7,
        "repetition_penalty": 1.2,
        "temperature": 0.7,
        "use_memory_cache": "on" if references else "off",
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
) -> Path:
    if not configured():
        raise RuntimeError("Fish Speech not configured — set CATTS_FISH_URL")

    payload = _payload(text, ref_audio=ref_audio, ref_text=ref_text)
    async with httpx.AsyncClient(timeout=300.0) as client:
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
) -> tuple[bytes, str]:
    if not configured():
        raise RuntimeError("Fish Speech not configured — set CATTS_FISH_URL")

    payload = _payload(text, ref_audio=ref_audio, ref_text=ref_text)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{FISH_URL}/v1/tts",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
    return _apply_speed(response.content), "fish"
