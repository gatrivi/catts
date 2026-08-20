from __future__ import annotations

import logging
import subprocess
import threading
import wave
from collections import OrderedDict
from pathlib import Path

from services.ffmpeg_util import ffmpeg_path

logger = logging.getLogger(__name__)

try:
    from pocket_tts import TTSModel  # type: ignore
except Exception:  # pragma: no cover
    TTSModel = None  # type: ignore

_model_lock = threading.Lock()
# lang_key -> loaded TTSModel (en / es need different weights)
_models: dict[str, object] = {}

_voice_state_cache_lock = threading.Lock()
_voice_state_cache: "OrderedDict[str, object]" = OrderedDict()
_MAX_VOICE_STATES = 4

_DEFAULT_VOICE_BY_LANG = {
    "en": "alba",
    "es": "lola",
}

# pocket-tts language ids (see TTSModel.load_model docstring)
_POCKET_LANG = {
    "en": "english",
    "es": "spanish_24l",
}


def available() -> bool:
    return TTSModel is not None


def ready() -> bool:
    return bool(_models)


def status_message() -> str:
    if TTSModel is None:
        return "pocket-tts not installed"
    if not _models:
        return "pocket-tts loading (first use)"
    return f"pocket-tts ready ({','.join(sorted(_models))})"


def _lang_key(lang: str) -> str:
    lang = (lang or "en").lower()
    if lang.startswith("es"):
        return "es"
    return "en"


def _pocket_language(lang: str) -> str:
    return _POCKET_LANG[_lang_key(lang)]


def _load_model(lang: str = "en"):
    key = _lang_key(lang)
    if key in _models:
        return _models[key]
    if TTSModel is None:
        raise RuntimeError("pocket-tts not installed")
    # Keep HF/torch caches on E:
    try:
        from scripts._local_cache import configure_project_cache

        configure_project_cache()
    except Exception:
        pass
    pocket_lang = _pocket_language(key)
    # ponytail: int8 helps ES a lot on Ryzen; still not live-realtime here (see TTS_RX6600_RESEARCH).
    logger.info("Loading pocket-tts language=%s quantize=True", pocket_lang)
    _models[key] = TTSModel.load_model(language=pocket_lang, quantize=True)
    return _models[key]


def warmup_model(lang: str = "en") -> None:
    """Best-effort preload; safe to call during startup."""
    if not available():
        return
    try:
        with _model_lock:
            _load_model(lang)
    except Exception as exc:  # pragma: no cover
        logger.warning("Pocket TTS warmup failed: %s", exc)


def _pick_voice(lang: str) -> str:
    return _DEFAULT_VOICE_BY_LANG[_lang_key(lang)]


def _voice_state_cache_get(key: str):
    with _voice_state_cache_lock:
        if key not in _voice_state_cache:
            return None
        _voice_state_cache.move_to_end(key)
        return _voice_state_cache[key]


def _voice_state_cache_put(key: str, value: object):
    with _voice_state_cache_lock:
        _voice_state_cache[key] = value
        _voice_state_cache.move_to_end(key)
        while len(_voice_state_cache) > _MAX_VOICE_STATES:
            _voice_state_cache.popitem(last=False)


def _voice_state_key(ref_audio: Path | None, lang: str) -> str:
    lk = _lang_key(lang)
    if ref_audio and ref_audio.exists():
        st = ref_audio.stat()
        return f"file:{ref_audio.resolve()}:{st.st_mtime_ns}:{st.st_size}:{lk}"
    return f"voice:{_pick_voice(lang)}:{lk}"


def _get_voice_state(ref_audio: Path | None, lang: str):
    with _model_lock:
        model = _load_model(lang)

    key = _voice_state_key(ref_audio, lang)
    cached = _voice_state_cache_get(key)
    if cached is not None:
        return model, cached

    if ref_audio and ref_audio.exists():
        prompt = str(ref_audio)
    else:
        prompt = _pick_voice(lang)

    voice_state = model.get_state_for_audio_prompt(prompt)
    _voice_state_cache_put(key, voice_state)
    return model, voice_state


def _to_int16_mono_pcm(audio, sample_rate: int) -> "tuple[int, bytes]":
    import numpy as np

    audio_np = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
    if audio_np.ndim > 1:
        audio_np = audio_np[0]

    if audio_np.dtype == np.int16:
        pcm = audio_np
    else:
        if np.issubdtype(audio_np.dtype, np.floating):
            audio_np = np.clip(audio_np, -1.0, 1.0)
            pcm = (audio_np * 32767.0).astype(np.int16)
        else:
            pcm = audio_np.astype(np.int16, copy=False)

    return sample_rate, pcm.tobytes()


def _write_wav_pcm16(out_path: Path, sample_rate: int, pcm16_bytes: bytes) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16_bytes)


def _maybe_resample_to_44100(src_wav: Path, dst_wav: Path, *, sample_rate: int) -> None:
    ffmpeg = ffmpeg_path()
    if not ffmpeg or sample_rate == 44100:
        if src_wav.resolve() != dst_wav.resolve():
            src_wav.replace(dst_wav)
        return

    subprocess.run(
        [ffmpeg, "-y", "-i", str(src_wav), "-ar", "44100", "-ac", "1", str(dst_wav)],
        check=True,
        capture_output=True,
    )
    src_wav.unlink(missing_ok=True)


async def synthesize(
    text: str,
    output_path: Path,
    ref_audio: Path | None = None,
    lang: str = "en",
) -> Path:
    if not available():
        raise RuntimeError("pocket-tts not installed — pip install pocket-tts")

    import asyncio

    def _run_sync():
        model, voice_state = _get_voice_state(ref_audio, lang)
        audio = model.generate_audio(voice_state, text)
        sr = int(getattr(model, "sample_rate", 24000))
        sr, pcm16_bytes = _to_int16_mono_pcm(audio, sr)

        tmp_wav = output_path.with_suffix(".pocket_tmp.wav")
        _write_wav_pcm16(tmp_wav, sr, pcm16_bytes)
        _maybe_resample_to_44100(tmp_wav, output_path, sample_rate=sr)
        return output_path

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync)
