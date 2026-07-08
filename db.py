"""SQLite persistence for jobs and voices."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata
from typing import Any

from config import DATA_DIR, DB_PATH, JOBS_DIR, VOICES_DIR


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT,
                progress REAL DEFAULT 0,
                message TEXT,
                voice_id TEXT,
                lang TEXT,
                callback_url TEXT,
                meta_json TEXT,
                result_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS voices (
                id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0,
                message TEXT,
                lang TEXT,
                sample_path TEXT,
                artifact_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def _slug_ascii(value: str) -> str:
    # ASCII-only, URL/path-safe. Keeps it short to avoid Windows path issues.
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def new_job_id(kind: str, meta: dict[str, Any] | None = None) -> str:
    # Human-ish: <kind>-<title-slug>-<8hex>. (IDs are also used as folder names.)
    # Keep a stable prefix for UI/UX readability.
    kind = "catts" if kind == "audiobook" else kind
    kind_slug = _slug_ascii(kind) or "job"
    title = ""
    if meta:
        title = str(meta.get("title") or "")
    title_slug = _slug_ascii(title)[:24] if title else ""
    if not title_slug:
        title_slug = "untitled"
    # Use UTC timestamp (ms) to keep it readable and avoid relying on hex.
    # Also reduces collision probability when multiple jobs are created close together.
    now = datetime.now(timezone.utc)
    ms = f"{int(now.microsecond / 1000):03d}"
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    suffix = f"{timestamp}-{ms}"
    job_id = f"{kind_slug}-{title_slug}-{suffix}"
    return job_id[:60]


def create_job(
    kind: str,
    voice_id: str | None = None,
    lang: str | None = None,
    callback_url: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    job_id = new_job_id(kind, meta)
    now = _utcnow()
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, kind, status, stage, progress, message, voice_id, lang,
                              callback_url, meta_json, created_at, updated_at)
            VALUES (?, ?, 'queued', 'uploaded', 0, 'Queued', ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                kind,
                voice_id,
                lang,
                callback_url,
                json.dumps(meta or {}),
                now,
                now,
            ),
        )
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = _utcnow()
    if "meta" in fields:
        fields["meta_json"] = json.dumps(fields.pop("meta"))
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", vals)


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_voices(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM voices ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_job(job_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    job_dir = JOBS_DIR / job_id
    if job_dir.exists():
        import shutil

        shutil.rmtree(job_dir, ignore_errors=True)
    return cur.rowcount > 0


def create_voice(name: str | None, lang: str, sample_path: str) -> str:
    voice_id = new_id()
    now = _utcnow()
    voice_dir = VOICES_DIR / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO voices (id, name, status, progress, message, lang, sample_path,
                                created_at, updated_at)
            VALUES (?, ?, 'queued', 0, 'Queued', ?, ?, ?, ?)
            """,
            (voice_id, name or voice_id, lang, sample_path, now, now),
        )
    return voice_id


def get_voice(voice_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM voices WHERE id = ?", (voice_id,)).fetchone()
    return dict(row) if row else None


def update_voice(voice_id: str, **fields) -> None:
    fields["updated_at"] = _utcnow()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [voice_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE voices SET {cols} WHERE id = ?", vals)


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def voice_dir(voice_id: str) -> Path:
    return VOICES_DIR / voice_id
