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
    default_voice_id: str | None = None


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
