import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.deps import require_api_key
from api.schemas import VoiceProgress, VoiceRename, VoiceStatus
from db import create_voice, get_voice, list_voices, update_voice, voice_dir
from services.job_runner import enqueue_voice
from services.reveal import reveal_in_folder
from services.voice_labels import sync_voice_labeled_files

router = APIRouter(prefix="/voices", tags=["voices"])

VOICE_SCRIPTS = {
    "en": """Welcome to CATTS voice training. Read this in your natural voice, calmly, as if narrating an audiobook.

My name is [say your name]. I am recording a personal voice for reading books and live interpretation.

The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.

One, two, three, four, five, six, seven, eight, nine, ten.

Some sentences are short. Others are longer, with pauses, questions, and variety in tone — but always natural.

How are you today? I hope you are well.

Thank you. This sample will teach CATTS to sound like me.""",
    "es": """Bienvenido al entrenamiento de voz de CATTS. Lee esto con tu voz natural, con calma, como si narraras un audiolibro.

Me llamo [di tu nombre]. Estoy grabando mi voz personal para libros y interpretación en vivo.

El veloz murciélago hindú comía feliz cardillo y kiwi.

Uno, dos, tres, cuatro, cinco, seis, siete, ocho, nueve, diez.

Algunas frases son cortas. Otras son más largas, con pausas y variedad de tono.

¿Cómo estás hoy? Espero que muy bien.

Gracias. Esta muestra enseñará a CATTS a sonar como yo.""",
}


def _normalize_sample(dest: Path, vdir: Path) -> Path:
    """Convert browser webm recordings to wav when ffmpeg is available."""
    if dest.suffix.lower() != ".webm":
        return dest
    if not shutil.which("ffmpeg"):
        return dest
    wav_dest = vdir / "sample.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(dest), "-ar", "44100", "-ac", "1", str(wav_dest)],
        check=True,
        capture_output=True,
    )
    dest.unlink(missing_ok=True)
    return wav_dest


@router.get("", response_model=list[VoiceProgress])
async def list_all_voices(limit: int = 50, _: None = Depends(require_api_key)):
    return [_voice_response(v) for v in list_voices(limit)]


def _voice_display(voice: dict) -> str:
    name = (voice.get("name") or "").strip()
    vid = voice.get("id") or ""
    if not name or name == vid or name.lower() in ("voice", "default"):
        name = "Mi voz principal" if (voice.get("lang") or "").startswith("es") else "My main voice"
    lang = voice.get("lang") or "en"
    lang_label = "Español" if lang.startswith("es") else "English"
    return f"{name} ({lang_label})"


def _voice_message(voice: dict) -> str:
    msg = voice.get("message") or ""
    if "stub mode" in msg.lower():
        return "Ready — preview sample saved (GPU worker needed to clone your real voice)"
    if voice.get("status") == "training":
        return msg or "Training in progress…"
    if voice.get("status") == "ready":
        return msg or "Ready to use"
    if voice.get("status") == "failed":
        return voice.get("error") or msg or "Training failed"
    return msg or "Queued"


def _voice_response(voice: dict) -> VoiceProgress:
    vdir = voice_dir(voice["id"])
    labeled = {}
    if vdir.exists():
        for key, suffix in (("sample", "_sample"), ("reference", "_reference")):
            for p in vdir.glob(f"*{suffix}.*"):
                if p.name.startswith("sample.") or p.name.startswith("reference."):
                    continue
                if "_EN_" in p.name or "_ES_" in p.name:
                    labeled[key] = p.name
                    break
    return VoiceProgress(
        id=voice["id"],
        name=voice.get("name"),
        display_name=_voice_display(voice),
        status=VoiceStatus(voice["status"]),
        progress=float(voice.get("progress") or 0),
        message=_voice_message(voice),
        lang=voice.get("lang"),
        ready=voice["status"] == "ready",
        error=voice.get("error"),
        folder=str(vdir.resolve()) if vdir.exists() else None,
        labeled_sample=labeled.get("sample"),
        labeled_reference=labeled.get("reference"),
    )


@router.get("/script/{lang}")
async def get_voice_script(lang: str):
    text = VOICE_SCRIPTS.get(lang, VOICE_SCRIPTS["en"])
    return {"lang": lang, "script": text}


@router.post("")
async def create_voice_job(
    sample: UploadFile = File(...),
    name: str | None = Form(None),
    lang: str = Form("en"),
    _: None = Depends(require_api_key),
):
    default = "Mi voz principal" if lang.startswith("es") else "My main voice"
    voice_id = create_voice((name or "").strip() or default, lang, "")
    vdir = voice_dir(voice_id)
    ext = Path(sample.filename or "sample.wav").suffix or ".webm"
    dest = vdir / f"sample{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(sample.file, f)

    try:
        dest = _normalize_sample(dest, vdir)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, "Failed to convert recording — try WAV/MP3 upload") from exc

    update_voice(voice_id, sample_path=str(dest))

    await enqueue_voice(voice_id)
    return {"voice_id": voice_id, "status": "queued"}


@router.patch("/{voice_id}")
async def rename_voice(voice_id: str, body: VoiceRename, _: None = Depends(require_api_key)):
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "Voice not found")
    update_voice(voice_id, name=body.name.strip())
    sync_voice_labeled_files(voice_id)
    return _voice_response(get_voice(voice_id))


@router.get("/{voice_id}/sample")
async def get_voice_sample(voice_id: str, _: None = Depends(require_api_key)):
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "Voice not found")
    vdir = voice_dir(voice_id)
    sync_voice_labeled_files(voice_id)
    for p in sorted(vdir.glob("*_sample.*")):
        if p.name.startswith("sample."):
            continue
        return FileResponse(p, media_type="application/octet-stream", filename=p.name)
    for name in ("sample.wav", "sample.webm", "sample.mp3"):
        path = vdir / name
        if path.exists():
            return FileResponse(path, media_type="application/octet-stream", filename=path.name)
    raise HTTPException(404, "No sample audio")


@router.post("/{voice_id}/reveal")
async def reveal_voice_folder(voice_id: str, _: None = Depends(require_api_key)):
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "Voice not found")
    vdir = voice_dir(voice_id)
    if not vdir.exists():
        raise HTTPException(404, "Voice folder missing")
    sync_voice_labeled_files(voice_id)
    reveal_in_folder(vdir)
    return {"opened": str(vdir.resolve())}


@router.get("/{voice_id}", response_model=VoiceProgress)
async def get_voice_status(voice_id: str, _: None = Depends(require_api_key)):
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "Voice not found")
    return _voice_response(voice)
