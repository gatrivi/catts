import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.deps import require_api_key
from services import stt_client, translate_client

router = APIRouter(prefix="/stt", tags=["stt"])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    from_lang: str = Field(..., pattern="^(en|es)$")
    to_lang: str = Field(..., pattern="^(en|es)$")


class TranslateResponse(BaseModel):
    text: str
    from_lang: str
    to_lang: str


class TranscribeResponse(BaseModel):
    text: str
    language: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    lang: str | None = Form(None),
    _: None = Depends(require_api_key),
):
    if lang and lang not in ("en", "es"):
        raise HTTPException(400, "lang must be en or es")
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        result = await stt_client.transcribe_file(tmp_path, lang=lang)
        return TranscribeResponse(
            text=result["text"],
            language=result.get("language") or lang or "auto",
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest, _: None = Depends(require_api_key)):
    try:
        out = translate_client.translate(req.text, req.from_lang, req.to_lang)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return TranslateResponse(text=out, from_lang=req.from_lang, to_lang=req.to_lang)
