"""OCR routes: fast (now) + batch (books / multi-image)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.deps import require_api_key
from services.ocr_client import (
    batch_configured,
    fast_configured,
    ocr_batch_images,
    ocr_batch_pdf,
    ocr_fast,
    ocr_image,
    ocr_pdf_via_worker_endpoint,
    save_ocr_markdown,
    worker_configured,
)

router = APIRouter(prefix="/ocr", tags=["ocr"])

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}


def _parse_titles(titles: str | None) -> list[str] | None:
    if not titles or not titles.strip():
        return None
    raw = titles.strip()
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except json.JSONDecodeError:
            pass
    return [t.strip() for t in raw.split("|") if t.strip()]


async def _run_batch(
    uploads: list[UploadFile],
    *,
    titles: str | None = None,
    title: str | None = None,
) -> dict:
    if not uploads:
        raise HTTPException(400, "Upload a PDF or one or more images")
    title_list = _parse_titles(titles)
    tmp_paths: list[Path] = []
    try:
        for up in uploads:
            fname = up.filename or "page.png"
            suffix = Path(fname).suffix.lower() or ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(await up.read())
                tmp_paths.append(Path(tmp.name))

        if len(tmp_paths) == 1 and tmp_paths[0].suffix.lower() == ".pdf":
            pages_done = {"n": 0, "total": 0}

            def on_progress(done: int, total: int, msg: str) -> None:
                pages_done["n"] = done
                pages_done["total"] = total

            text = await ocr_batch_pdf(tmp_paths[0], on_progress=on_progress)
            out = save_ocr_markdown(text, kind="batch", title=title)
            return {
                "text": text,
                "filename": uploads[0].filename,
                "path": str(out),
                "mode": "batch",
                "pages": pages_done["total"] or 1,
            }

        for p in tmp_paths:
            suf = p.suffix.lower()
            if suf == ".pdf":
                raise HTTPException(400, "Upload one PDF alone, or images only (not mixed)")
            if suf not in _IMAGE_SUFFIXES:
                raise HTTPException(400, f"Unsupported file type: {p.suffix}")

        text = await ocr_batch_images(tmp_paths, titles=title_list)
        out = save_ocr_markdown(text, kind="batch", title=title)
        return {
            "text": text,
            "filename": uploads[0].filename,
            "path": str(out),
            "mode": "batch",
            "pages": len(tmp_paths),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"OCR worker failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        for p in tmp_paths:
            if p.exists():
                p.unlink(missing_ok=True)


@router.post("/fast")
async def ocr_fast_upload(
    file: UploadFile = File(...),
    page: int = Form(0),
    title: str | None = Form(None),
    _: None = Depends(require_api_key),
):
    """Fast OCR for one page/image — seconds, local Tesseract."""
    if not fast_configured():
        raise HTTPException(503, "Fast OCR disabled. Set CATTS_OCR_FAST=tesseract.")
    fname = file.filename or "page.png"
    suffix = Path(fname).suffix.lower() or ".png"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        if suffix == ".pdf":
            text = await ocr_fast(pdf_path=tmp_path, page_index=max(0, page))
        else:
            text = await ocr_fast(image_path=tmp_path)
        out = save_ocr_markdown(text, kind="fast", title=title)
        return {"text": text, "filename": fname, "path": str(out), "mode": "fast"}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"OCR polish failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.post("/batch")
async def ocr_batch_upload(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    titles: str | None = Form(None),
    title: str | None = Form(None),
    _: None = Depends(require_api_key),
):
    """Batch OCR: PDF or N images. Writes data/ocr/*-batch.md."""
    if not batch_configured():
        raise HTTPException(
            503,
            "Batch OCR not configured. Set CATTS_OCR_BATCH=omniroute|unlimited|tesseract "
            "(and OmniRoute URL or WORKER_URL as needed).",
        )
    uploads = list(files or [])
    if file is not None:
        uploads.insert(0, file)
    return await _run_batch(uploads, titles=titles, title=title)


@router.post("/image")
async def ocr_image_upload(
    file: UploadFile = File(...),
    prompt: str = Form("document parsing."),
    _: None = Depends(require_api_key),
):
    """Legacy: single image. Prefer POST /ocr/batch or /ocr/fast."""
    if worker_configured():
        suffix = Path(file.filename or "image.png").suffix or ".png"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(await file.read())
                tmp_path = Path(tmp.name)
            text = await ocr_image(tmp_path, prompt=prompt)
            out = save_ocr_markdown(text, kind="batch")
            return {"text": text, "filename": file.filename, "path": str(out), "mode": "batch"}
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"OCR worker failed: {exc}") from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    if not batch_configured():
        raise HTTPException(503, "OCR worker not configured. Set CATTS_WORKER_URL or CATTS_OCR_BATCH.")
    return await _run_batch([file])


@router.post("/pdf")
async def ocr_pdf_upload(
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    """Legacy PDF OCR. Prefer POST /ocr/batch."""
    if worker_configured():
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(await file.read())
                tmp_path = Path(tmp.name)
            text = await ocr_pdf_via_worker_endpoint(tmp_path)
            out = save_ocr_markdown(text, kind="batch")
            return {"text": text, "filename": file.filename, "path": str(out), "mode": "batch"}
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"OCR worker failed: {exc}") from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    if not batch_configured():
        raise HTTPException(503, "OCR worker not configured. Set CATTS_WORKER_URL or WORKER_URL or CATTS_OCR_BATCH.")
    return await _run_batch([file])
