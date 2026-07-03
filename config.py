import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CATTS_DATA_DIR", BASE_DIR / "data"))
JOBS_DIR = DATA_DIR / "jobs"
VOICES_DIR = DATA_DIR / "voices"

API_HOST = os.getenv("CATTS_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("CATTS_API_PORT", "59200"))
API_KEY = os.getenv("CATTS_API_KEY", "")

WORKER_URL = os.getenv("CATTS_WORKER_URL", "").rstrip("/")
OCR_ENGINE = os.getenv("CATTS_OCR_ENGINE", "none")  # unlimited | none
TTS_ENGINE = os.getenv("CATTS_TTS_ENGINE", "xtts")  # xtts | edge | chatterbox | gptsovits
DEFAULT_VOICE_ID = os.getenv("CATTS_DEFAULT_VOICE_ID", "").strip()

MAX_CONCURRENT_JOBS = int(os.getenv("CATTS_MAX_CONCURRENT_JOBS", "1"))
TTS_CHUNK_MIN = int(os.getenv("CATTS_TTS_CHUNK_MIN", "200"))
TTS_CHUNK_MAX = int(os.getenv("CATTS_TTS_CHUNK_MAX", "400"))
PDF_OCR_DPI = int(os.getenv("CATTS_PDF_OCR_DPI", "300"))
KEEP_INTERMEDIATE_AUDIO = os.getenv("CATTS_KEEP_INTERMEDIATES", "false").lower() in ("1", "true", "yes")

DB_PATH = DATA_DIR / "catts.db"
