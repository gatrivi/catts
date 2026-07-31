import io
import os


os.environ.setdefault("CATTS_WORKER_URL", "")
os.environ.setdefault("CATTS_OCR_BATCH", "none")
os.environ.setdefault("CATTS_OCR_FAST", "none")
os.environ.setdefault("CATTS_OMNIROUTE_URL", "")

from fastapi.testclient import TestClient

from api.main import app


def test_ocr_image_requires_worker():
    client = TestClient(app)
    response = client.post(
        "/ocr/image",
        files={"file": ("image.png", io.BytesIO(b"not-an-image"), "image/png")},
    )
    assert response.status_code == 503
    assert "OCR" in response.text or "configured" in response.text


def test_ocr_pdf_requires_worker():
    client = TestClient(app)
    response = client.post(
        "/ocr/pdf",
        files={"file": ("book.pdf", io.BytesIO(b"%PDF-1.7"), "application/pdf")},
    )
    assert response.status_code == 503
    assert "OCR" in response.text or "configured" in response.text


def test_ocr_fast_requires_engine():
    client = TestClient(app)
    response = client.post(
        "/ocr/fast",
        files={"file": ("page.png", io.BytesIO(b"not-an-image"), "image/png")},
    )
    assert response.status_code == 503
    assert "Fast OCR" in response.text


def test_ocr_batch_requires_engine():
    client = TestClient(app)
    response = client.post(
        "/ocr/batch",
        files={"file": ("page.png", io.BytesIO(b"not-an-image"), "image/png")},
    )
    assert response.status_code == 503
    assert "Batch OCR" in response.text
