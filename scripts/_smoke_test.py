"""Stage-exact CATTS smoke test (API + STT + Translate + Voice + Audio decode)."""

from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path

import httpx

from services.audio_silence import is_not_silent, to_wav_if_needed


BASE = os.getenv("CATTS_API_BASE", "http://127.0.0.1:59200").rstrip("/")
SILENCE_PEAK_THRESHOLD = float(os.getenv("CATTS_SILENCE_PEAK_THRESHOLD", "0.008"))


def _headers() -> dict[str, str]:
    key = os.getenv("CATTS_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def _write_sine_wav(out_path: Path, *, duration_sec: float, sr: int = 16000, freq: float = 220.0, amp: float = 0.25) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_sec * sr)
    amp = max(0.0, min(float(amp), 1.0))
    amp_i16 = int(amp * 32767)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n_frames):
            t = i / sr
            v = int(amp_i16 * math.sin(2.0 * math.pi * freq * t))
            wf.writeframesraw(struct.pack("<h", v))


def _fail(stage: str, detail: str) -> "None":
    print(f"FAIL stage={stage} — {detail}")
    raise SystemExit(1)


def _skip(stage: str, reason: str) -> "None":
    print(f"SKIP stage={stage} — {reason}")


def _ok(stage: str, detail: str = "") -> "None":
    print(f"OK   stage={stage}" + (f" — {detail}" if detail else ""))


def main() -> int:
    client = httpx.Client(timeout=180.0)
    headers = _headers()

    def translate(health: dict) -> None:
        if not health.get("translate_ready"):
            _skip("translate", "translate not installed")
            return
        r = client.post(
            f"{BASE}/stt/translate",
            json={"text": "Hello world", "from_lang": "en", "to_lang": "es"},
            headers=headers,
            timeout=120.0,
        )
        if r.status_code != 200:
            _fail("translate", f"HTTP {r.status_code}: {r.text[:200]}")
        _ok("translate", r.json().get("text", "")[:60])

    def stt_transcribe(tmp: Path, health: dict) -> None:
        if (health.get("stt_engine") or "none") != "whisper":
            _skip("stt_transcribe", f"stt_engine={health.get('stt_engine')}")
            return
        wav = tmp / "stt_test.wav"
        _write_sine_wav(wav, duration_sec=0.9, amp=0.25, freq=220.0)
        with wav.open("rb") as f:
            r = client.post(
                f"{BASE}/stt/transcribe",
                files={"file": (wav.name, f, "audio/wav")},
                data={"lang": "en"},
                headers=headers,
                timeout=240.0,
            )
        if r.status_code != 200:
            _fail("stt_transcribe", f"HTTP {r.status_code}: {r.text[:200]}")
        d = r.json()
        _ok("stt_transcribe", f"lang={d.get('language')} preview={(d.get('text') or '')[:50]}")

    def voice_train(tmp: Path) -> str:
        sample = tmp / "voice_sample.wav"
        _write_sine_wav(sample, duration_sec=1.2, amp=0.25, freq=200.0)
        with sample.open("rb") as f:
            r = client.post(
                f"{BASE}/voices",
                files={"sample": (sample.name, f, "audio/wav")},
                data={"name": "Smoke Voice", "lang": "en"},
                headers=headers,
                timeout=180.0,
            )
        if r.status_code != 200:
            _fail("voice_train", f"HTTP {r.status_code}: {r.text[:200]}")
        vid = r.json().get("voice_id")
        if not vid:
            _fail("voice_train", "voice_id missing from response")

        # Poll until stub training marks ready or failed.
        deadline = time.time() + 180.0
        while time.time() < deadline:
            v = client.get(f"{BASE}/voices/{vid}", headers=headers, timeout=60.0).json()
            if v.get("ready") is True:
                _ok("voice_train", f"{vid[:8]} ready")
                return vid
            if v.get("status") == "failed":
                _fail("voice_train", f"failed: {v.get('error') or v.get('message')}")
            time.sleep(2.0)

        _fail("voice_train", "timeout waiting voice ready")

    def audiobook_job_audio(tmp: Path, voice_id: str) -> tuple[str, Path]:
        book_txt = tmp / "book.txt"
        book_txt.write_text(
            "This is a short smoke test book.\n\nChapter 1\nThis tiny chapter validates audiobook pipeline.",
            encoding="utf-8",
        )

        with book_txt.open("rb") as f:
            r = client.post(
                f"{BASE}/jobs/audiobook",
                files={"file": (book_txt.name, f, "text/plain")},
                data={
                    "voice_id": voice_id,
                    "lang": "en",
                    "title": "Smoke Book",
                    "author": "CATTS",
                    "chapter_mode": "number",
                    "generate_audio": "true",
                },
                headers=headers,
                timeout=180.0,
            )
        if r.status_code != 200:
            _fail("audiobook_job_audio", f"HTTP {r.status_code}: {r.text[:200]}")
        job_id = r.json().get("job_id")
        if not job_id:
            _fail("audiobook_job_audio", "job_id missing from response")

        deadline = time.time() + 240.0
        while time.time() < deadline:
            j = client.get(f"{BASE}/jobs/{job_id}", headers=headers, timeout=60.0).json()
            if j.get("status") == "done":
                break
            if j.get("status") in ("failed", "cancelled"):
                _fail("audiobook_job_audio", f"{j.get('status')}: {j.get('error') or j.get('message')}")
            time.sleep(2.0)

        else:
            _fail("audiobook_job_audio", "timeout waiting job done")

        ra = client.get(f"{BASE}/jobs/{job_id}/chapters/1/audio", headers=headers, timeout=120.0)
        if ra.status_code != 200 or not ra.content:
            _fail("audiobook_job_audio", f"chapter audio missing: HTTP {ra.status_code}")

        content_type = (ra.headers.get("content-type") or "").lower()
        suffix = ".wav" if "wav" in content_type else ".mp3"
        audio_path = tmp / f"chapter1{suffix}"
        audio_path.write_bytes(ra.content)
        _ok("audiobook_job_audio", f"job={job_id[:8]} audio={suffix} bytes={len(ra.content)}")
        return job_id, audio_path

    def audio_decode_peak_check(audio_path: Path) -> None:
        wav_path = to_wav_if_needed(audio_path)
        if audio_path.suffix.lower() != ".wav" and wav_path is None:
            _skip("audio_decode_peak_check", "ffmpeg missing; can't verify silence for non-wav audio")
            return

        ok, peak = is_not_silent(audio_path, threshold_peak=SILENCE_PEAK_THRESHOLD)
        if not ok:
            _fail("audio_decode_peak_check", f"audio seems silent (peak={peak:.4f} < {SILENCE_PEAK_THRESHOLD})")
        _ok("audio_decode_peak_check", f"peak={peak:.4f}")

    def tts_live(health: dict, voice_id: str, tmp: Path) -> None:
        if not (health.get("xtts_installed") and health.get("xtts_ready")):
            _skip("tts_live", f"XTTS not ready (installed={health.get('xtts_installed')}, ready={health.get('xtts_ready')})")
            return

        r = client.post(
            f"{BASE}/tts/live",
            json={"text": "Hello this is a CATTS smoke test", "voice_id": voice_id, "lang": "en"},
            headers={**headers, "Content-Type": "application/json"},
            timeout=240.0,
        )
        if r.status_code != 200:
            _fail("tts_live", f"HTTP {r.status_code}: {r.text[:200]}")
        if not r.content or len(r.content) < 1000:
            _fail("tts_live", f"empty audio bytes={len(r.content) if r.content else 0}")

        out = tmp / "live_tts.wav"
        out.write_bytes(r.content)
        ok, peak = is_not_silent(out, threshold_peak=SILENCE_PEAK_THRESHOLD)
        if not ok:
            _fail("tts_live", f"live audio silent (peak={peak:.4f})")
        _ok("tts_live", f"engine={r.headers.get('X-TTS-Engine','?')} peak={peak:.4f} bytes={len(r.content)}")

    # ---- Run stages ----
    print(f"=== CATTS smoke @ {BASE} ===")
    tmp_root = tempfile.mkdtemp(prefix="catts_smoke_")
    tmp = Path(tmp_root)

    # health
    try:
        h = client.get(f"{BASE}/health", headers=headers, timeout=20.0).json()
    except Exception as e:
        _fail("health", str(e))
    _ok(
        "health",
        f"tts={h.get('tts_engine')} stt={h.get('stt_engine')} xtts_ready={h.get('xtts_ready')}",
    )

    # translate
    try:
        translate(h)
    except Exception as e:
        _fail("translate", str(e))

    # stt_transcribe
    try:
        stt_transcribe(tmp, h)
    except Exception as e:
        _fail("stt_transcribe", str(e))

    # voice_train
    voice_id = voice_train(tmp)

    # audiobook_job_audio + audio_decode_peak_check
    job_id, audio_path = audiobook_job_audio(tmp, voice_id)
    audio_decode_peak_check(audio_path)

    # tts_live (conditional)
    try:
        h2 = client.get(f"{BASE}/health", headers=headers, timeout=20.0).json()
        tts_live(h2, voice_id, tmp)
    except Exception as e:
        _fail("tts_live", str(e))

    print("=== SMOKE OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
