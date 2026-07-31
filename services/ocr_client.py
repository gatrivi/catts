"""Dual-path OCR: fast (Tesseract) + batch (OmniRoute / Unlimited / Tesseract)."""

from __future__ import annotations

import base64
import json
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

import httpx

from config import (
    OCR_BATCH,
    OCR_DIR,
    OCR_ENGINE,
    OCR_FAST,
    OCR_FAST_POLISH,
    OMNIROUTE_API_KEY,
    OMNIROUTE_URL,
    OMNIROUTE_VISION_MODEL,
    PDF_OCR_DPI,
    WORKER_URL,
)
from text_processor import strip_ocr_noise

logger = logging.getLogger(__name__)

_BATCH_PROMPT = (
    "Extract all readable text from this page image. "
    "Preserve line breaks and stanza/paragraph structure. "
    "Do not add commentary. Output plain text only."
)


def worker_configured() -> bool:
    return bool(WORKER_URL)


def fast_configured() -> bool:
    return OCR_FAST not in ("", "none")


def batch_configured() -> bool:
    if OCR_BATCH in ("", "none") and OCR_ENGINE not in ("unlimited",):
        return False
    engine = _resolve_batch_engine()
    if engine == "unlimited":
        return bool(WORKER_URL)
    if engine == "omniroute":
        return bool(OMNIROUTE_URL)
    if engine == "tesseract":
        return True
    return False


def _resolve_batch_engine() -> str:
    """Pick batch engine; fall back unlimited→omniroute→tesseract when misconfigured."""
    engine = OCR_BATCH if OCR_BATCH not in ("", "none") else (
        "unlimited" if OCR_ENGINE == "unlimited" else "none"
    )
    if engine == "unlimited" and not WORKER_URL:
        engine = "omniroute" if OMNIROUTE_URL else "tesseract"
    if engine == "omniroute" and not OMNIROUTE_URL:
        engine = "unlimited" if WORKER_URL else "tesseract"
    return engine


async def check_worker_health() -> bool:
    if not WORKER_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{WORKER_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


def normalize_ocr_layout(text: str) -> str:
    """Light layout normalize: keep stanza breaks, join soft hyphenation."""
    text = strip_ocr_noise(text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop trailing spaces per line; keep blank lines (stanzas).
    lines = [ln.rstrip() for ln in text.split("\n")]
    text = "\n".join(lines)
    text = text.replace("\u00ad", "")  # soft hyphen
    return text.strip()


def ensure_ocr_dir() -> Path:
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    return OCR_DIR


def save_ocr_markdown(text: str, kind: str = "fast", title: str | None = None) -> Path:
    """Write cleaned text to data/ocr/<stamp>-{kind}.md."""
    ensure_ocr_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OCR_DIR / f"{stamp}-{kind}.md"
    body = text.strip()
    if title:
        body = f"# {title}\n\n{body}"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def pdf_to_images(pdf_path: Path, dpi: int = PDF_OCR_DPI) -> list[Path]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pymupdf required for PDF OCR") from exc

    doc = fitz.open(pdf_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="catts_pdf_"))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    paths: list[Path] = []
    for i, page in enumerate(doc):
        out = tmp_dir / f"page_{i + 1:04d}.png"
        page.get_pixmap(matrix=mat).save(out)
        paths.append(out)
    doc.close()
    return paths


def pdf_page_to_image(pdf_path: Path, page_index: int = 0, dpi: int = PDF_OCR_DPI) -> Path:
    """Render a single PDF page (0-based) to a temp PNG."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pymupdf required for PDF OCR") from exc

    doc = fitz.open(pdf_path)
    if page_index < 0 or page_index >= len(doc):
        doc.close()
        raise ValueError(f"PDF page index out of range: {page_index}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="catts_pdf_page_"))
    out = tmp_dir / f"page_{page_index + 1:04d}.png"
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    doc[page_index].get_pixmap(matrix=mat).save(out)
    doc.close()
    return out


def pdf_page_count(pdf_path: Path) -> int:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pymupdf required for PDF OCR") from exc
    doc = fitz.open(pdf_path)
    n = len(doc)
    doc.close()
    return n


def _encode_image(image_path: Path) -> dict:
    ext = image_path.suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.') or 'png'}"
    data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def _configure_tesseract() -> None:
    """Point pytesseract at the binary if not already on PATH."""
    import pytesseract

    if shutil.which("tesseract"):
        return
    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path.home() / r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    for cand in candidates:
        if cand.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(cand)
            return


def _tesseract_image(image_path: Path, lang: str = "eng+spa") -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Fast OCR needs pytesseract and Pillow. "
            "Install: pip install pytesseract pillow; install Tesseract OCR binary."
        ) from exc

    _configure_tesseract()
    img = Image.open(image_path)
    try:
        raw = pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractError:
        raw = pytesseract.image_to_string(img, lang="eng")
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract binary not found. Install UB-Mannheim Tesseract OCR "
            "or add tesseract.exe to PATH."
        ) from exc
    return normalize_ocr_layout(raw)


async def _omniroute_vision(image_path: Path, prompt: str = _BATCH_PROMPT) -> str:
    if not OMNIROUTE_URL:
        raise RuntimeError("CATTS_OMNIROUTE_URL not set for batch OCR")
    content = [
        {"type": "text", "text": prompt},
        _encode_image(image_path),
    ]
    payload = {
        "model": OMNIROUTE_VISION_MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if OMNIROUTE_API_KEY:
        headers["Authorization"] = f"Bearer {OMNIROUTE_API_KEY}"
    url = f"{OMNIROUTE_URL}/chat/completions"
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(url, headers=headers, content=json.dumps(payload))
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
    return normalize_ocr_layout(text)


async def _unlimited_image(image_path: Path, prompt: str = "document parsing.") -> str:
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
        return normalize_ocr_layout(data["choices"][0]["message"]["content"])


# --- Public API ---


async def ocr_fast(
    image_path: Path | None = None,
    *,
    pdf_path: Path | None = None,
    page_index: int = 0,
    polish: bool | None = None,
) -> str:
    """Fast path: Tesseract on one image or one PDF page."""
    if OCR_FAST in ("", "none"):
        raise RuntimeError("Fast OCR disabled (CATTS_OCR_FAST=none)")
    if image_path is None and pdf_path is None:
        raise ValueError("Provide image_path or pdf_path")
    path = image_path
    cleanup: Path | None = None
    if path is None:
        path = pdf_page_to_image(pdf_path, page_index=page_index)  # type: ignore[arg-type]
        cleanup = path.parent
    try:
        if OCR_FAST != "tesseract":
            raise RuntimeError(f"Unsupported CATTS_OCR_FAST={OCR_FAST}")
        text = _tesseract_image(path)
        do_polish = OCR_FAST_POLISH if polish is None else polish
        if do_polish and OMNIROUTE_URL:
            # Optional one-shot vision re-read (heavier; off by default).
            text = await _omniroute_vision(
                path,
                prompt=(
                    "Transcribe this page accurately. Preserve line and stanza breaks. "
                    "Output plain text only."
                ),
            )
        return text
    finally:
        if cleanup and cleanup.exists():
            shutil.rmtree(cleanup, ignore_errors=True)


async def ocr_batch_page(image_path: Path, engine: str | None = None) -> str:
    """Quality OCR for one page image."""
    eng = (engine or _resolve_batch_engine()).lower()
    try:
        if eng == "unlimited":
            return await _unlimited_image(image_path, prompt=_BATCH_PROMPT)
        if eng == "omniroute":
            return await _omniroute_vision(image_path)
        if eng == "tesseract":
            return _tesseract_image(image_path)
        raise RuntimeError(f"No batch OCR engine available (got {eng})")
    except Exception as exc:
        if eng in ("omniroute", "unlimited") and eng != "tesseract":
            logger.warning("Batch OCR %s failed (%s); falling back to tesseract", eng, exc)
            return _tesseract_image(image_path)
        raise


async def ocr_batch_images(
    image_paths: list[Path],
    *,
    titles: list[str] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    on_page: Callable[[int, int, str], None] | None = None,
    engine: str | None = None,
) -> str:
    """OCR N images in order; optional section titles between pages."""
    total = len(image_paths)
    if total == 0:
        return ""
    pages: list[str] = []
    for idx, image_path in enumerate(image_paths, start=1):
        if on_progress:
            on_progress(idx - 1, total, f"OCR page {idx}/{total}")
        text = await ocr_batch_page(image_path, engine=engine)
        title = None
        if titles and idx - 1 < len(titles) and titles[idx - 1]:
            title = titles[idx - 1].strip()
        elif titles is None and total > 1:
            first = (text.split("\n", 1)[0] or "").strip()
            # Only promote clear headings (not poem/body first lines).
            if first and len(first) <= 60 and (
                first.isupper()
                or first.lower().startswith(("chapter ", "capítulo ", "part ", "parte "))
            ):
                title = first
        block = f"## {title}\n\n{text}" if title else text
        pages.append(block)
        if on_page:
            on_page(idx, total, "\n\n".join(pages))
        if on_progress:
            on_progress(idx, total, f"OCR page {idx}/{total}")
    return "\n\n".join(pages)


async def ocr_batch_pdf(
    pdf_path: Path,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
    on_page: Callable[[int, int, str], None] | None = None,
    engine: str | None = None,
) -> str:
    """Page-1-first PDF OCR: callback after each page with cumulative text."""
    images = pdf_to_images(pdf_path)
    try:
        return await ocr_batch_images(
            images,
            on_progress=on_progress,
            on_page=on_page,
            engine=engine,
        )
    finally:
        if images:
            shutil.rmtree(images[0].parent, ignore_errors=True)


# --- Legacy Unlimited helpers (compat) ---


def _pdf_to_images(pdf_path: Path, dpi: int = PDF_OCR_DPI) -> list[Path]:
    return pdf_to_images(pdf_path, dpi=dpi)


async def ocr_pdf(
    pdf_path: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> str:
    """Run Unlimited-OCR on a PDF via GPU worker (legacy)."""
    return await ocr_batch_pdf(pdf_path, on_progress=on_progress, engine="unlimited")


async def ocr_image(image_path: Path, prompt: str = "document parsing.") -> str:
    """Run OCR on a single image via Unlimited worker (legacy)."""
    return await _unlimited_image(image_path, prompt=prompt)


async def ocr_pdf_via_worker_endpoint(
    pdf_path: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> str:
    """Delegate full PDF OCR to worker /ocr/pdf if available; else page-by-page batch."""
    if WORKER_URL:
        async with httpx.AsyncClient(timeout=1200.0) as client:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                data = {"dpi": str(PDF_OCR_DPI)}
                r = await client.post(f"{WORKER_URL}/ocr/pdf", files=files, data=data)
            if r.status_code != 404:
                r.raise_for_status()
                result = r.json()
                if on_progress:
                    on_progress(result.get("pages", 1), result.get("pages", 1), "OCR complete")
                return normalize_ocr_layout(result["text"])
    return await ocr_batch_pdf(pdf_path, on_progress=on_progress)
