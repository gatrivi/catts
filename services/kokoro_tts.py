"""Kokoro ONNX (fastkokoro) client — OpenAI-compatible speech API."""

from pathlib import Path

import httpx

from config import KOKORO_URL, KOKORO_VOICE, KOKORO_VOICE_ES


def configured() -> bool:
    return bool(KOKORO_URL)


async def ready() -> bool:
    if not configured():
        return False
    try:
        # This is polled by the UI; keep an offline server from stalling the page.
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{KOKORO_URL}/v1/audio/voices")
        return response.status_code < 500
    except Exception:
        return False


def status_message(is_ready: bool) -> str:
    if is_ready:
        return f"Kokoro ready at {KOKORO_URL}"
    return f"Kokoro not reachable at {KOKORO_URL} — start scripts/start_kokoro.ps1"


async def synthesize(text: str, output_path: Path, lang: str = "en") -> Path:
    # FastKokoro is language-aware for G2P (phoneme conversion).
    language = "es" if str(lang).startswith("es") else "en-us"
    voice_id = KOKORO_VOICE_ES if str(lang).startswith("es") else KOKORO_VOICE
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice_id,
        "response_format": "wav",
        "speed": 1.0,
        "lang": language,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=payload)
        response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path


async def live_tts(text: str, lang: str = "en") -> tuple[bytes, str]:
    language = "es" if str(lang).startswith("es") else "en-us"
    voice_id = KOKORO_VOICE_ES if str(lang).startswith("es") else KOKORO_VOICE
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice_id,
        "response_format": "wav",
        "speed": 1.0,
        "lang": language,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=payload)
        response.raise_for_status()
    return response.content, "kokoro"
