import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.deps import require_api_key
from services.ocr_client import ocr_image, ocr_pdf_via_worker_endpoint, worker_configured

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/image")
async def ocr_image_upload(
    file: UploadFile = File(...),
    prompt: str = Form("document parsing."),
    _: None = Depends(require_api_key),
):
    if not worker_configured():
        raise HTTPException(503, "OCR worker not configured. Set CATTS_WORKER_URL to an Unlimited-OCR worker.")
    suffix = Path(file.filename or "image.png").suffix or ".png"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        text = await ocr_image(tmp_path, prompt=prompt)
        return {"text": text, "filename": file.filename}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"OCR worker failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.post("/pdf")
async def ocr_pdf_upload(
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    if not worker_configured():
        raise HTTPException(503, "OCR worker not configured. Set CATTS_WORKER_URL to an Unlimited-OCR worker.")
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        text = await ocr_pdf_via_worker_endpoint(tmp_path)
        return {"text": text, "filename": file.filename}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"OCR worker failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
