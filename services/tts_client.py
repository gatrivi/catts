"""TTS: XTTS (local clone) → Chatterbox → GPT-SoVITS worker → Edge TTS fallback."""

import logging
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import httpx

from config import TTS_ENGINE, WORKER_URL
from services import chatterbox_tts, xtts_tts

logger = logging.getLogger(__name__)

EDGE_VOICES = {
    "en": "en-US-AriaNeural",
    "es": "es-ES-AlvaroNeural",
}


def engine_label() -> str:
    if TTS_ENGINE == "gptsovits" and WORKER_URL:
        return "gptsovits"
    if TTS_ENGINE in ("xtts", "stub", "chatterbox") and xtts_tts.available():
        return "xtts"
    if TTS_ENGINE in ("chatterbox", "stub") and chatterbox_tts.available():
        return "chatterbox"
    return "edge"


def _clone_engines() -> list[str]:
    order: list[str] = []
    if TTS_ENGINE in ("xtts", "stub", "chatterbox") and xtts_tts.available():
        order.append("xtts")
    if TTS_ENGINE in ("chatterbox", "stub") and chatterbox_tts.available():
        order.append("chatterbox")
    return order


async def _local_clone(text: str, output_path: Path, ref_audio: Path, lang: str) -> Path:
    last_exc: Exception | None = None
    for name in _clone_engines():
        try:
            if name == "xtts":
                return await xtts_tts.synthesize(text, output_path, ref_audio, lang)
            return await chatterbox_tts.synthesize(text, output_path, ref_audio)
        except Exception as exc:
            last_exc = exc
            logger.warning("%s failed (%s)", name, exc)
    if last_exc:
        raise last_exc
    raise RuntimeError("no local clone engine available")


def _silent_wav(path: Path, duration_sec: float = 0.4, sample_rate: int = 22050) -> None:
    n_frames = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<h", 0) * n_frames)


def _mp3_to_wav(mp3: Path, wav: Path) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)],
        check=True,
        capture_output=True,
    )
    return True


async def _edge_tts(text: str, output_path: Path, lang: str = "en") -> Path:
    import edge_tts

    voice = EDGE_VOICES.get(lang[:2], EDGE_VOICES["en"])
    mp3_path = output_path.with_suffix(".mp3")
    await edge_tts.Communicate(text, voice).save(str(mp3_path))
    if _mp3_to_wav(mp3_path, output_path):
        mp3_path.unlink(missing_ok=True)
        return output_path
    return mp3_path


async def synthesize(
    text: str,
    output_path: Path,
    voice_id: str | None = None,
    lang: str = "en",
    ref_audio: Path | None = None,
) -> Path:
    if TTS_ENGINE == "gptsovits" and WORKER_URL:
        return await _synthesize_gptsovits(text, output_path, voice_id, lang, ref_audio)

    if ref_audio and _clone_engines():
        try:
            return await _local_clone(text, output_path, ref_audio, lang)
        except Exception as exc:
            logger.warning("Local clone failed (%s), falling back to Edge TTS", exc)

    try:
        result = await _edge_tts(text, output_path, lang)
        return result if result.suffix == ".mp3" else output_path
    except Exception as exc:
        logger.warning("edge-tts failed (%s), using silent placeholder", exc)
        _silent_wav(output_path, duration_sec=0.3)
        return output_path


async def _synthesize_gptsovits(
    text: str,
    output_path: Path,
    voice_id: str | None,
    lang: str,
    ref_audio: Path | None,
) -> Path:
    payload = {
        "text": text,
        "text_lang": lang,
        "ref_audio_path": str(ref_audio) if ref_audio else "",
        "prompt_text": "",
        "prompt_lang": lang,
        "voice_id": voice_id or "",
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{WORKER_URL}/tts/synthesize", json=payload)
        r.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(r.content)
    return output_path


async def live_tts(text: str, voice_id: str, lang: str = "en", ref_audio: Path | None = None) -> bytes:
    if TTS_ENGINE == "gptsovits" and WORKER_URL:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{WORKER_URL}/tts/live",
                json={"text": text, "voice_id": voice_id, "lang": lang},
            )
            r.raise_for_status()
            return r.content

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "live.wav"
        if ref_audio and _clone_engines():
            try:
                await _local_clone(text, out, ref_audio, lang)
                return out.read_bytes()
            except Exception as exc:
                logger.warning("Local clone live failed (%s)", exc)
        try:
            result = await _edge_tts(text, out, lang)
            return result.read_bytes()
        except Exception:
            _silent_wav(out, duration_sec=0.5)
            return out.read_bytes()
