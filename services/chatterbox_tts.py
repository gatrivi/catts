"""Local voice-clone TTS via Resemble Chatterbox (CPU / AMD / NVIDIA)."""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_device = "cpu"


def available() -> bool:
    try:
        import chatterbox  # noqa: F401
        return True
    except ImportError:
        return False


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


def _load_model():
    global _model, _device
    if _model is not None:
        return _model
    from chatterbox.tts import ChatterboxTTS

    _device = _pick_device()
    logger.info("Loading Chatterbox on %s (first run downloads ~1GB model)", _device)
    _model = ChatterboxTTS.from_pretrained(device=_device)
    return _model


def _generate_sync(text: str, ref_audio: Path | None, output_path: Path) -> Path:
    import torchaudio as ta

    model = _load_model()
    kwargs = {}
    if ref_audio and ref_audio.exists():
        kwargs["audio_prompt_path"] = str(ref_audio)
    wav = model.generate(text[:2000], **kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(output_path), wav, model.sr)
    return output_path


async def synthesize(text: str, output_path: Path, ref_audio: Path | None = None) -> Path:
    if not available():
        raise RuntimeError("chatterbox-tts not installed — pip install chatterbox-tts torch torchaudio")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_sync, text, ref_audio, output_path)
