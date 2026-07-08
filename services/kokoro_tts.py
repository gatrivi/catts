"""Kokoro-FastAPI client using its OpenAI-compatible speech API."""

from pathlib import Path

import httpx

from config import KOKORO_URL, KOKORO_VOICE


def configured() -> bool:
    return bool(KOKORO_URL)


async def ready() -> bool:
    if not configured():
        return False
    try:
        # Some first-run/container/CPU contention cases can exceed a very small timeout
        # even when the service is reachable (e.g. model warmup, slow response).
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{KOKORO_URL}/v1/audio/voices")
        return response.status_code < 500
    except Exception:
        return False


def status_message(is_ready: bool) -> str:
    if is_ready:
        return f"Kokoro ready at {KOKORO_URL}"
    return f"Kokoro not reachable at {KOKORO_URL} — start Kokoro-FastAPI first"


async def synthesize(text: str, output_path: Path, lang: str = "en") -> Path:
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": KOKORO_VOICE,
        "response_format": "wav",
        "speed": 1.0,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=payload)
        response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path


async def live_tts(text: str, lang: str = "en") -> tuple[bytes, str]:
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": KOKORO_VOICE,
        "response_format": "wav",
        "speed": 1.0,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=payload)
        response.raise_for_status()
    return response.content, "kokoro"
