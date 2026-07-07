"""Unlimited-OCR worker client (SGLang OpenAI-compatible API)."""

import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Callable

import httpx

from config import PDF_OCR_DPI, WORKER_URL

logger = logging.getLogger(__name__)


def worker_configured() -> bool:
    return bool(WORKER_URL)


async def check_worker_health() -> bool:
    if not WORKER_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{WORKER_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


def _pdf_to_images(pdf_path: Path, dpi: int = PDF_OCR_DPI) -> list[Path]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pymupdf required for local PDF OCR fallback") from exc

    doc = fitz.open(pdf_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="catts_pdf_"))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    paths = []
    for i, page in enumerate(doc):
        out = tmp_dir / f"page_{i + 1:04d}.png"
        page.get_pixmap(matrix=mat).save(out)
        paths.append(out)
    doc.close()
    return paths


def _encode_image(image_path: Path) -> dict:
    ext = image_path.suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
    data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


async def ocr_pdf(
    pdf_path: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> str:
    """Run Unlimited-OCR on a PDF via GPU worker."""
    if not WORKER_URL:
        raise RuntimeError("CATTS_WORKER_URL not configured for OCR")

    images = _pdf_to_images(pdf_path)
    total = len(images)
    if on_progress:
        on_progress(0, total, "PDF converted to images")

    pages_text: list[str] = []
    async with httpx.AsyncClient(timeout=1200.0) as client:
        for idx, image_path in enumerate(images, start=1):
            content = [
                {"type": "text", "text": "Multi page parsing."},
                _encode_image(image_path),
            ]
            payload = {
                "model": "Unlimited-OCR",
                "messages": [{"role": "user", "content": content}],
                "temperature": 0,
                "stream": False,
                "images_config": {"image_mode": "base"},
            }
            r = await client.post(
                f"{WORKER_URL}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            pages_text.append(text.strip())
            if on_progress:
                on_progress(idx, total, f"OCR page {idx}/{total}")

    return "\n\n".join(pages_text)


async def ocr_image(image_path: Path, prompt: str = "document parsing.") -> str:
    """Run OCR on a single image via the configured Unlimited-OCR worker."""
    if not WORKER_URL:
        raise RuntimeError("CATTS_WORKER_URL not configured for OCR")
    content = [
        {"type": "text", "text": prompt or "document parsing."},
        _encode_image(image_path),
    ]
    payload = {
        "model": "Unlimited-OCR",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "stream": False,
        "images_config": {"image_mode": "gundam"},
    }
    async with httpx.AsyncClient(timeout=1200.0) as client:
        r = await client.post(
            f"{WORKER_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


async def ocr_pdf_via_worker_endpoint(
    pdf_path: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> str:
    """Delegate full PDF OCR to worker /ocr/pdf endpoint if available."""
    if not WORKER_URL:
        raise RuntimeError("CATTS_WORKER_URL not configured for OCR")

    async with httpx.AsyncClient(timeout=1200.0) as client:
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data = {"dpi": str(PDF_OCR_DPI)}
            r = await client.post(f"{WORKER_URL}/ocr/pdf", files=files, data=data)
        if r.status_code == 404:
            return await ocr_pdf(pdf_path, on_progress=on_progress)
        r.raise_for_status()
        result = r.json()
        if on_progress:
            on_progress(result.get("pages", 1), result.get("pages", 1), "OCR complete")
        return result["text"]
