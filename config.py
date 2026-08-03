import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    from scripts._local_cache import configure_project_cache

    configure_project_cache()
except Exception:
    pass

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

DATA_DIR = Path(os.getenv("CATTS_DATA_DIR", BASE_DIR / "data"))
JOBS_DIR = DATA_DIR / "jobs"
VOICES_DIR = DATA_DIR / "voices"

API_HOST = os.getenv("CATTS_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("CATTS_API_PORT", "59200"))
API_KEY = os.getenv("CATTS_API_KEY", "")

WORKER_URL = os.getenv("CATTS_WORKER_URL", "").rstrip("/")
# Legacy: unlimited | none. Prefer CATTS_OCR_FAST / CATTS_OCR_BATCH.
OCR_ENGINE = os.getenv("CATTS_OCR_ENGINE", "none")  # unlimited | none
# Fast = "read this page now"; batch = books (quality, page-1-first).
OCR_FAST = os.getenv("CATTS_OCR_FAST", "tesseract").strip().lower()  # tesseract | none
OCR_BATCH = os.getenv("CATTS_OCR_BATCH", "omniroute").strip().lower()  # omniroute | unlimited | tesseract | none
OCR_FAST_POLISH = os.getenv("CATTS_OCR_FAST_POLISH", "").lower() in ("1", "true", "yes")
OCR_DIR = DATA_DIR / "ocr"
# OmniRoute / OpenAI-compatible vision hub for batch OCR cleanup
OMNIROUTE_URL = os.getenv("CATTS_OMNIROUTE_URL", "http://127.0.0.1:20128/v1").rstrip("/")
OMNIROUTE_API_KEY = os.getenv("CATTS_OMNIROUTE_API_KEY", "").strip()
OMNIROUTE_VISION_MODEL = os.getenv(
    "CATTS_OMNIROUTE_VISION_MODEL", "openrouter/free"
).strip()
TTS_ENGINE = os.getenv("CATTS_TTS_ENGINE", "kokoro")  # kokoro | melotts | edge | xtts | pocket | fish | chatterbox | gptsovits
KOKORO_URL = os.getenv("CATTS_KOKORO_URL", "http://127.0.0.1:8880").rstrip("/")
KOKORO_VOICE = os.getenv("CATTS_KOKORO_VOICE", "af_bella").strip()
KOKORO_VOICE_ES = os.getenv("CATTS_KOKORO_VOICE_ES", "ef_dora").strip()
# Piper is legacy/optional. Spanish stays on native Kokoro unless explicitly enabled.
PIPER_URL = os.getenv("CATTS_PIPER_URL", "").rstrip("/")
DEFAULT_VOICE_ID = os.getenv("CATTS_DEFAULT_VOICE_ID", "").strip()

# Fish Speech (patientx/fish-speech-zluda / local Fish-compatible server)
FISH_URL = os.getenv("CATTS_FISH_URL", "http://127.0.0.1:8080").rstrip("/")
FISH_MODEL = os.getenv("CATTS_FISH_MODEL", "s2-pro").strip()
# Fish 1.5 API has no speed field — client may stretch via ffmpeg atempo
try:
    TTS_SPEED = float(os.getenv("CATTS_TTS_SPEED", "0.9"))
except ValueError:
    TTS_SPEED = 0.9
TTS_SPEED = max(0.5, min(TTS_SPEED, 2.0))
# If unset, we try to pick a Spanish voice from /v1/voices (if the server supports it).
FISH_REFERENCE_ID = os.getenv("CATTS_FISH_REFERENCE_ID", "").strip() or None
FISH_REFERENCE_ID_ES = os.getenv("CATTS_FISH_REFERENCE_ID_ES", "").strip() or None
STT_MODEL = os.getenv("CATTS_STT_MODEL", "small")  # faster-whisper: tiny|base|small|medium
ACCEPT_COQUI_CPML = os.getenv("CATTS_ACCEPT_COQUI_CPML", "").lower() in ("1", "true", "yes")

MAX_CONCURRENT_JOBS = int(os.getenv("CATTS_MAX_CONCURRENT_JOBS", "1"))
# Fish: fewer/larger chunks = less per-chunk overhead on ZLUDA (default bumped).
TTS_CHUNK_MIN = int(os.getenv("CATTS_TTS_CHUNK_MIN", "400"))
TTS_CHUNK_MAX = int(os.getenv("CATTS_TTS_CHUNK_MAX", "800"))
PDF_OCR_DPI = int(os.getenv("CATTS_PDF_OCR_DPI", "300"))
KEEP_INTERMEDIATE_AUDIO = os.getenv("CATTS_KEEP_INTERMEDIATES", "false").lower() in ("1", "true", "yes")

DB_PATH = DATA_DIR / "catts.db"

OMP_BIN = os.getenv("CATTS_OMP_BIN", "").strip()
OMP_MODEL = os.getenv("CATTS_OMP_MODEL", "lm-studio/ornith-1.0-9b")
OMP_CWD = os.getenv("CATTS_OMP_CWD", str(BASE_DIR))
OMP_TIMEOUT_SEC = int(os.getenv("CATTS_OMP_TIMEOUT_SEC", "300"))

# Text translation (offline)
# - argos: Argos Translate via subprocess (.venv)
# - madlad: google/madlad400-3b-mt via a persistent worker (.venv)
TRANSLATE_ENGINE = os.getenv("CATTS_TRANSLATE_ENGINE", "auto").strip().lower()  # argos | madlad | auto

MADLAD_MODEL_ID = os.getenv("CATTS_MADLAD_MODEL_ID", "google/madlad400-3b-mt").strip()
MADLAD_MODEL_DIR = Path(
    os.getenv("CATTS_MADLAD_MODEL_DIR", str(DATA_DIR / "madlad_runtime" / "model"))
)
MADLAD_DEVICE = os.getenv("CATTS_MADLAD_DEVICE", "cpu").strip()  # cpu

# Quality knobs for offline translation.
MADLAD_NUM_BEAMS = int(os.getenv("CATTS_MADLAD_NUM_BEAMS", "4"))
MADLAD_MAX_NEW_TOKENS = int(os.getenv("CATTS_MADLAD_MAX_NEW_TOKENS", "256"))
MADLAD_SPLIT_SENTENCES = os.getenv("CATTS_MADLAD_SPLIT_SENTENCES", "1").lower() in ("1", "true", "yes")
