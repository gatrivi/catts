"""Self-check for Fish Speech client payload + config (no live server)."""

from __future__ import annotations

import base64
from pathlib import Path

from services.fish_tts import _payload, configured, status_message


def test_payload_with_ref(tmp_path: Path):
    wav = tmp_path / "ref.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")
    body = _payload("hola mundo", ref_audio=wav, ref_text="hola")
    assert body["text"] == "hola mundo"
    assert body["format"] == "wav"
    assert body["use_memory_cache"] == "on"
    assert len(body["references"]) == 1
    decoded = base64.b64decode(body["references"][0]["audio"])
    assert decoded.startswith(b"RIFF")
    assert body["references"][0]["text"] == "hola"


def test_payload_without_ref():
    body = _payload("hello")
    assert body["references"] == []
    assert body["use_memory_cache"] == "off"


def test_status_and_configured(monkeypatch):
    monkeypatch.setattr("services.fish_tts.FISH_URL", "http://127.0.0.1:8080")
    assert configured() is True
    assert "8080" in status_message(True)
    assert "start_fish_api" in status_message(False)
