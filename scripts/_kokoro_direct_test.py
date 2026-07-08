import httpx

url = "http://127.0.0.1:8880/v1/audio/speech"
payload = {
    "model": "kokoro",
    "input": "Direct Kokoro test",
    "voice": "af_bella",
    "response_format": "wav",
    "speed": 1.0,
}

r = httpx.post(url, json=payload, timeout=120)
print("status", r.status_code)
print("content_type", r.headers.get("content-type"))
print("bytes", len(r.content))

