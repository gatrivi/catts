import httpx
import pytest


@pytest.mark.parametrize(
    ("text", "voice", "lang"),
    [
        ("Direct Kokoro test", "af_bella", "en-us"),
        ("Prueba directa de Kokoro en español", "ef_dora", "es"),
    ],
)
def test_kokoro_direct_smoke(text: str, voice: str, lang: str):
    url = "http://127.0.0.1:8880/v1/audio/speech"
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": "wav",
        "speed": 1.0,
        "lang": lang,
    }

    try:
        r = httpx.post(url, json=payload, timeout=120)
    except httpx.RequestError as exc:
        pytest.skip(f"Kokoro not reachable at {url}: {exc}", allow_module_level=False)

    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/")
    assert len(r.content) > 0

