"""Local voice-clone TTS via Resemble Chatterbox (CPU / AMD / NVIDIA)."""

import asyncio
import importlib.util
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_device = "cpu"


@lru_cache(maxsize=1)
def available() -> bool:
    # Engine discovery is polled by the UI. Importing Chatterbox here loads a
    # large dependency tree and can freeze unrelated sample playback.
    return importlib.util.find_spec("chatterbox") is not None


@lru_cache(maxsize=1)
def _pick_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


_mtl_model = None


def _load_model(lang: str = "en"):
    """EN uses ChatterboxTTS; other langs use ChatterboxMultilingualTTS."""
    global _model, _mtl_model, _device
    _device = _pick_device()
    use_mtl = not str(lang).lower().startswith("en")
    if use_mtl:
        if _mtl_model is not None:
            return _mtl_model, True
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        logger.info("Loading Chatterbox Multilingual on %s (first run downloads model)", _device)
        try:
            _mtl_model = ChatterboxMultilingualTTS.from_pretrained(device=_device, t3_model="v3")
        except TypeError:
            _mtl_model = ChatterboxMultilingualTTS.from_pretrained(device=_device)
        return _mtl_model, True

    if _model is not None:
        return _model, False
    from chatterbox.tts import ChatterboxTTS

    logger.info("Loading Chatterbox EN on %s (first run downloads ~1GB model)", _device)
    _model = ChatterboxTTS.from_pretrained(device=_device)
    return _model, False


def _generate_sync(
    text: str,
    ref_audio: Path | None,
    output_path: Path,
    lang: str = "en",
) -> Path:
    import torchaudio as ta

    model, is_mtl = _load_model(lang)
    kwargs = {}
    if ref_audio and ref_audio.exists():
        kwargs["audio_prompt_path"] = str(ref_audio)
    chunk = text[:2000]
    if is_mtl:
        lang_id = "es" if str(lang).lower().startswith("es") else str(lang).lower()[:2]
        wav = model.generate(chunk, language_id=lang_id, **kwargs)
    else:
        wav = model.generate(chunk, **kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(output_path), wav, model.sr)
    return output_path


async def synthesize(
    text: str,
    output_path: Path,
    ref_audio: Path | None = None,
    lang: str = "en",
) -> Path:
    if not available():
        raise RuntimeError("chatterbox-tts not installed — pip install chatterbox-tts torch torchaudio")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_sync, text, ref_audio, output_path, lang)
