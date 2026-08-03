"""Self-check for Fish Speech client payload + voice lock (no live server)."""

from __future__ import annotations

import base64
import struct
import wave
from pathlib import Path

import pytest

from services.ffmpeg_util import change_tempo
from services.fish_tts import _payload, configured, resolve_fish_ref, status_message


def test_payload_with_ref(tmp_path: Path):
    wav = tmp_path / "ref.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")
    body = _payload("hola mundo", ref_audio=wav, ref_text="hola")
    assert body["text"] == "hola mundo"
    assert body["format"] == "wav"
    assert body["use_memory_cache"] == "on"
    assert body["seed"] == 42
    assert len(body["references"]) == 1
    decoded = base64.b64decode(body["references"][0]["audio"])
    assert decoded.startswith(b"RIFF")
    assert body["references"][0]["text"] == "hola"


def test_payload_without_ref_allowed_for_struct_only():
    body = _payload("hello", require_ref=False)
    assert body["references"] == []


def test_payload_require_ref_raises():
    with pytest.raises(RuntimeError, match="without reference"):
        _payload("hello", require_ref=True)


def test_resolve_fish_ref_locks_same_file(tmp_path: Path, monkeypatch):
    voices = tmp_path / "voices" / "gaston-en"
    voices.mkdir(parents=True)
    ref = voices / "fish_ref_en_15s.wav"
    ref.write_bytes(b"x" * 2000)
    monkeypatch.setattr("services.fish_tts.VOICES_DIR", tmp_path / "voices")
    monkeypatch.setattr("services.fish_tts.DEFAULT_VOICE_ID", "gaston-en")
    a = resolve_fish_ref(lang="en", voice_id="gaston-en")
    b = resolve_fish_ref(lang="en", voice_id="gaston-en")
    assert a == b == ref


def test_resolve_fish_ref_missing_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("services.fish_tts.VOICES_DIR", tmp_path / "voices")
    monkeypatch.setattr("services.fish_tts.DEFAULT_VOICE_ID", "")
    (tmp_path / "voices").mkdir()
    with pytest.raises(RuntimeError, match="locked reference"):
        resolve_fish_ref(lang="en", voice_id=None)


def test_status_and_configured(monkeypatch):
    monkeypatch.setattr("services.fish_tts.FISH_URL", "http://127.0.0.1:8080")
    assert configured() is True
    assert "8080" in status_message(True)
    assert "start_fish" in status_message(False)


def test_change_tempo_noop(tmp_path: Path):
    src = tmp_path / "a.wav"
    dst = tmp_path / "b.wav"
    with wave.open(str(src), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(struct.pack("<h", 1000) * 2205)
    out = change_tempo(src, dst, 1.0)
    assert out == dst
    assert dst.read_bytes() == src.read_bytes()
