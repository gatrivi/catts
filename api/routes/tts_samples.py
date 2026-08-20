"""Public, browser-playable TTS quality samples."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import DATA_DIR

router = APIRouter(prefix="/tts/samples", tags=["tts"])

SAMPLES_DIR = DATA_DIR / "tts_tests"
SAMPLES = {
    "edge-es-ar": {
        "label": "Edge TTS es-AR-TomasNeural",
        "filename": "edge_es_ar_tomas.wav",
    },
    "kokoro-es": {
        "label": "FastKokoro ef_dora (ES)",
        "filename": "kokoro_ef_dora.wav",
    },
    "melotts-es": {
        "label": "MeloTTS Spanish (preset)",
        "filename": "melotts_ruisenor_sample.wav",
    },
    "chatterbox-latam-v3": {
        "label": "Chatterbox LatAm V3 (Gaston clone)",
        "filename": "chatterbox_quality_es_sample.wav",
    },
    "chatterbox-gaston": {
        "label": "Chatterbox Multilingual (Gaston ref)",
        "filename": "chatterbox_gaston_es.wav",
    },
}


@router.get("")
async def list_tts_samples():
    """List only the curated comparison samples; never enumerate the data folder."""
    return {
        "samples": [
            {
                "id": sample_id,
                "label": sample["label"],
                "url": f"/tts/samples/{sample_id}.wav",
                "available": (SAMPLES_DIR / sample["filename"]).is_file(),
            }
            for sample_id, sample in SAMPLES.items()
        ]
    }


@router.get("/{sample_id}.wav", response_class=FileResponse)
async def get_tts_sample(sample_id: str):
    """Stream one allowlisted WAV inline so browsers can play it directly."""
    sample = SAMPLES.get(sample_id)
    if sample is None:
        raise HTTPException(404, "Unknown TTS sample")

    path: Path = SAMPLES_DIR / sample["filename"]
    if not path.is_file():
        raise HTTPException(404, "TTS sample is not available")

    return FileResponse(
        path,
        media_type="audio/wav",
        filename=sample["filename"],
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )
