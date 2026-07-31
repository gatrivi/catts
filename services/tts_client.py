"""TTS client (local/worker engines) with sensible fallbacks."""

import logging
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import httpx

from config import WORKER_URL
from services import chatterbox_tts, fish_tts, kokoro_tts, melotts_tts, pocket_tts, xtts_tts
from services.ffmpeg_util import ffmpeg_path
from services.tts_runtime import get_engine

logger = logging.getLogger(__name__)

try:
    from scripts.tts_text_prep import prep_for_tts
except Exception:  # pragma: no cover — import path when cwd differs
    def prep_for_tts(text: str) -> str:
        import re

        return re.sub(r"\s+", " ", (text or "").replace("\r\n", "\n")).strip()


EDGE_VOICES = {
    "en": "en-US-AriaNeural",
    # LatAm (AR), not Iberian — see docs/ACCENT_CORDOBA.md
    "es": "es-AR-TomasNeural",
}


def engine_label() -> str:
    eng = get_engine()
    if eng == "fish" and fish_tts.configured():
        return "fish"
    if eng == "kokoro" and kokoro_tts.configured():
        return "kokoro"
    if eng == "melotts" and melotts_tts.available():
        return "melotts"
    if eng == "pocket" and pocket_tts.available():
        return "pocket"
    if eng == "gptsovits" and WORKER_URL:
        return "gptsovits"
    if eng == "xtts" and xtts_tts.available():
        return "xtts"
    if eng == "chatterbox" and chatterbox_tts.available():
        return "chatterbox"
    if eng == "edge":
        return "edge"
    # requested engine not ready — still report intent so UI can show status
    if eng in ("fish", "kokoro", "melotts", "xtts", "pocket", "chatterbox", "gptsovits"):
        return eng
    return "edge"


def _clone_engines() -> list[str]:
    eng = get_engine()
    order: list[str] = []
    if eng in ("pocket", "stub") and pocket_tts.available():
        order.append("pocket")
    if eng in ("xtts", "stub") and xtts_tts.available():
        order.append("xtts")
    if eng in ("chatterbox", "stub") and chatterbox_tts.available():
        order.append("chatterbox")
    # when explicitly on a clone engine, prefer that one only
    if eng == "pocket" and "pocket" not in order and pocket_tts.available():
        order = ["pocket"]
    if eng == "xtts" and "xtts" not in order and xtts_tts.available():
        order = ["xtts"]
    if eng == "chatterbox" and "chatterbox" not in order and chatterbox_tts.available():
        order = ["chatterbox"]
    return order


async def _local_clone(text: str, output_path: Path, ref_audio: Path, lang: str) -> Path:
    last_exc: Exception | None = None
    for name in _clone_engines():
        try:
            if name == "xtts":
                return await xtts_tts.synthesize(text, output_path, ref_audio, lang)
            if name == "pocket":
                return await pocket_tts.synthesize(text, output_path, ref_audio=ref_audio, lang=lang)
            return await chatterbox_tts.synthesize(text, output_path, ref_audio, lang=lang)
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
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        return False
    subprocess.run(
        [ffmpeg, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)],
        check=True,
        capture_output=True,
    )
    return True


async def _edge_tts(text: str, output_path: Path, lang: str = "en") -> Path:
    import edge_tts

    voice = EDGE_VOICES.get(lang[:2], EDGE_VOICES["en"])
    spoken = prep_for_tts(text)  # no line-break pauses — ever
    mp3_path = output_path.with_suffix(".mp3")
    await edge_tts.Communicate(spoken, voice).save(str(mp3_path))
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
    eng = get_engine()

    if eng == "gptsovits" and WORKER_URL:
        return await _synthesize_gptsovits(text, output_path, voice_id, lang, ref_audio)

    if eng == "fish" and fish_tts.configured():
        return await fish_tts.synthesize(text, output_path, lang=lang, voice_id=voice_id, ref_audio=ref_audio)

    if eng == "kokoro" and kokoro_tts.configured():
        return await kokoro_tts.synthesize(text, output_path, lang)

    if eng == "melotts":
        if not str(lang).lower().startswith("es"):
            raise RuntimeError("MeloTTS supports Spanish only")
        if not melotts_tts.available():
            raise RuntimeError("TTS engine 'melotts' is selected but not ready")
        return await melotts_tts.synthesize(text, output_path, lang)

    if eng == "pocket" and pocket_tts.available():
        return await pocket_tts.synthesize(text, output_path, ref_audio=ref_audio, lang=lang)

    if eng == "chatterbox" and chatterbox_tts.available():
        return await chatterbox_tts.synthesize(text, output_path, ref_audio, lang=lang)

    if eng == "xtts" and ref_audio and xtts_tts.available():
        return await xtts_tts.synthesize(text, output_path, ref_audio, lang)

    if ref_audio and _clone_engines():
        try:
            return await _local_clone(text, output_path, ref_audio, lang)
        except Exception as exc:
            if voice_id:
                raise RuntimeError(f"Voice clone failed: {exc}") from exc
            logger.warning("Local clone failed (%s), falling back to Edge TTS", exc)

    if eng not in ("edge", "stub") and eng in (
        "fish",
        "kokoro",
        "melotts",
        "xtts",
        "pocket",
        "chatterbox",
        "gptsovits",
    ):
        raise RuntimeError(f"TTS engine '{eng}' is selected but not ready")

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


async def live_tts(text: str, voice_id: str, lang: str = "en", ref_audio: Path | None = None) -> tuple[bytes, str]:
    """Returns (audio_bytes, engine_used)."""
    eng = get_engine()

    if eng == "gptsovits" and WORKER_URL:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{WORKER_URL}/tts/live",
                json={"text": text, "voice_id": voice_id, "lang": lang},
            )
            r.raise_for_status()
            return r.content, "gptsovits"

    if eng == "fish" and fish_tts.configured():
        return await fish_tts.live_tts(text, voice_id, lang, ref_audio=ref_audio)

    if eng == "kokoro" and kokoro_tts.configured():
        return await kokoro_tts.live_tts(text, lang)

    if eng == "melotts":
        if not str(lang).lower().startswith("es"):
            raise RuntimeError("MeloTTS supports Spanish only")
        if not melotts_tts.available():
            raise RuntimeError("TTS engine 'melotts' is selected but not ready")
        return await melotts_tts.live_tts(text, lang)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "live.wav"
        if eng == "chatterbox" and chatterbox_tts.available():
            await chatterbox_tts.synthesize(text, out, ref_audio, lang=lang)
            return out.read_bytes(), "chatterbox"
        if eng == "xtts" and ref_audio and xtts_tts.available():
            await xtts_tts.synthesize(text, out, ref_audio, lang)
            return out.read_bytes(), "xtts"
        if eng == "pocket" and pocket_tts.available():
            await pocket_tts.synthesize(text, out, ref_audio=ref_audio, lang=lang)
            return out.read_bytes(), "pocket"
        if eng == "edge":
            result = await _edge_tts(text, out, lang)
            return result.read_bytes(), "edge"
        if ref_audio and _clone_engines():
            await _local_clone(text, out, ref_audio, lang)
            return out.read_bytes(), engine_label()

        if eng in ("xtts", "pocket", "chatterbox"):
            raise RuntimeError(
                f"Engine '{eng}' needs a voice sample — save reference.wav, or switch engine in the UI."
            )

        try:
            result = await _edge_tts(text, out, lang)
            return result.read_bytes(), "edge"
        except Exception:
            _silent_wav(out, duration_sec=0.5)
            return out.read_bytes(), "silent"
