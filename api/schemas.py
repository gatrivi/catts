from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class VoiceStatus(str, Enum):
    queued = "queued"
    training = "training"
    ready = "ready"
    failed = "failed"


class HealthResponse(BaseModel):
    status: str
    worker_reachable: bool
    worker_url: str
    ocr_engine: str
    tts_engine: str  # xtts | edge | gptsovits
    tts_ready: bool = False
    tts_message: str = ""
    stt_engine: str  # whisper | none
    translate_ready: bool
    default_voice_id: str | None = None
    xtts_installed: bool = False
    xtts_ready: bool = False
    xtts_message: str = ""


class JobProgress(BaseModel):
    id: str
    kind: str
    status: JobStatus
    stage: str
    progress: float = Field(ge=0, le=100)
    message: str
    voice_id: str | None = None
    lang: str | None = None
    title: str | None = None
    author: str | None = None
    display_name: str | None = None
    chapters_done: int | None = None
    chapters_total: int | None = None
    manuscript_ready: bool = False
    result_ready: bool = False
    error: str | None = None


class JobSummary(BaseModel):
    id: str
    status: JobStatus
    stage: str
    progress: float
    message: str
    title: str | None = None
    author: str | None = None
    display_name: str | None = None
    created_at: str | None = None
    error: str | None = None
    result_ready: bool = False


class JobMetadataPatch(BaseModel):
    title: str | None = None
    author: str | None = None
    chapter_mode: str | None = None


class JobFiles(BaseModel):
    job_id: str
    folder: str
    audiobook_path: str | None = None
    audiobook_name: str | None = None
    manuscript_md: str | None = None
    manuscript_txt: str | None = None
    chapters: list[dict] = []
    playable: bool = False


class VoiceProgress(BaseModel):
    id: str
    name: str | None = None
    display_name: str | None = None
    status: VoiceStatus
    progress: float = Field(ge=0, le=100)
    message: str
    lang: str | None = None
    ready: bool = False
    error: str | None = None
    folder: str | None = None
    labeled_sample: str | None = None
    labeled_reference: str | None = None
    has_sample: bool = False
    sample_bytes: int | None = None
    sample_duration_sec: float | None = None
    script_match: float | None = None
    script_match_label: str | None = None
    transcript_preview: str | None = None
    quality_status: str = "unchecked"


class VoiceRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class LiveTTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    voice_id: str
    lang: str = Field(default="en", pattern="^(en|es)$")


class LiveTTSResponse(BaseModel):
    voice_id: str
    lang: str
    duration_ms: int | None = None
    engine: str


class AgentPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=32000)
    model: str | None = None
    cwd: str | None = None
    auto_approve: bool = True
    timeout_sec: int | None = Field(default=None, ge=10, le=3600)


class AgentPromptResponse(BaseModel):
    ok: bool
    text: str
    session_id: str | None = None
    exit_code: int
    stderr: str | None = None
    event_count: int = 0
