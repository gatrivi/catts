"""Async audiobook and voice job pipeline."""

import asyncio
import json
import logging
import shutil
from pathlib import Path

from config import MAX_CONCURRENT_JOBS, OCR_ENGINE, TTS_CHUNK_MAX, TTS_CHUNK_MIN
from db import get_job, get_voice, job_dir, update_job
from services.audiobook_mux import concat_audio, package_audiobook
from services.ingest import extract_text
from services.job_cleanup import cleanup_job_artifacts
from services.voice_labels import label_job_chapters
from services.job_manifest import write_job_readme
from services.ocr_client import ocr_pdf_via_worker_endpoint
from services.tts_client import engine_label, synthesize
from services.voice_trainer import run_voice_training
from text_processor import chapters_to_markdown, chapters_to_plain, process_book

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_running = 0
_queue: asyncio.Queue[str] = asyncio.Queue()
_voice_queue: asyncio.Queue[str] = asyncio.Queue()


def _meta(job: dict) -> dict:
    raw = job.get("meta_json") or "{}"
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def _set_meta(job_id: str, **kwargs) -> None:
    job = get_job(job_id)
    if not job:
        return
    meta = _meta(job)
    meta.update(kwargs)
    update_job(job_id, meta=meta)


async def enqueue_audiobook(job_id: str) -> None:
    await _queue.put(job_id)
    asyncio.create_task(_drain())


async def enqueue_voice(voice_id: str) -> None:
    await _voice_queue.put(voice_id)
    asyncio.create_task(_drain_voices())


async def _drain_voices() -> None:
    while not _voice_queue.empty():
        voice_id = await _voice_queue.get()
        try:
            await run_voice_training(voice_id)
        except Exception:
            logger.exception("Voice job failed: %s", voice_id)


async def _drain() -> None:
    global _running
    async with _lock:
        if _running >= MAX_CONCURRENT_JOBS:
            return
        if _queue.empty():
            return
        job_id = await _queue.get()
        _running += 1

    try:
        await _run_audiobook(job_id)
    except Exception as exc:
        logger.exception("Audiobook job failed: %s", job_id)
        update_job(job_id, status="failed", message="Job failed", error=str(exc))
    finally:
        async with _lock:
            _running -= 1
        if not _queue.empty():
            asyncio.create_task(_drain())


async def _run_audiobook(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    if job["status"] == "cancelled":
        return

    jdir = job_dir(job_id)
    update_job(job_id, status="running", stage="uploaded", progress=2, message="Starting")

    meta = _meta(job)
    generate_audio = meta.get("generate_audio", True)
    audio_only = meta.get("audio_only", False)

    if audio_only and (jdir / "chapters.json").exists():
        meta.pop("audio_only", None)
        update_job(job_id, meta=meta)
        chapters = json.loads((jdir / "chapters.json").read_text(encoding="utf-8"))
        await _render_audiobook_audio(job_id, jdir, job, chapters, meta)
        return

    text_path = jdir / "input.txt"
    pdf_path = jdir / "input.pdf"
    epub_path = jdir / "input.epub"
    docx_path = jdir / "input.docx"
    text = ""
    book_title = meta.get("title", "Audiobook")
    book_author = meta.get("author", "")
    chapter_mode = meta.get("chapter_mode", "detect")
    book_lang = job.get("lang") or meta.get("lang")

    if text_path.exists():
        text = text_path.read_text(encoding="utf-8")
        update_job(job_id, stage="text_processing", progress=15, message="Using provided text")
    elif epub_path.exists():
        update_job(job_id, stage="ingest", progress=10, message="Extracting EPUB text")
        text = extract_text(epub_path)
        (jdir / "extracted.txt").write_text(text, encoding="utf-8")
    elif docx_path.exists():
        update_job(job_id, stage="ingest", progress=10, message="Extracting DOCX text")
        text = extract_text(docx_path)
        (jdir / "extracted.txt").write_text(text, encoding="utf-8")
    elif pdf_path.exists():
        update_job(job_id, stage="ingest", progress=10, message="Extracting PDF text")
        try:
            text = extract_text(pdf_path)
            (jdir / "extracted.txt").write_text(text, encoding="utf-8")
        except ValueError as exc:
            if OCR_ENGINE == "unlimited":
                update_job(job_id, stage="ocr", progress=5, message="No text layer — running OCR")

                def ocr_progress(done: int, total: int, msg: str) -> None:
                    pct = 5 + (done / max(total, 1)) * 40
                    update_job(job_id, stage="ocr", progress=pct, message=msg)

                text = await ocr_pdf_via_worker_endpoint(pdf_path, on_progress=ocr_progress)
                (jdir / "ocr_output.txt").write_text(text, encoding="utf-8")
            else:
                raise RuntimeError(str(exc)) from exc
    else:
        raise RuntimeError("No input file found for job")

    update_job(job_id, stage="text_processing", progress=50, message="Processing chapters")
    chapters = process_book(
        text, TTS_CHUNK_MIN, TTS_CHUNK_MAX,
        title=book_title, author=book_author,
        chapter_mode=chapter_mode, lang=book_lang,
    )
    (jdir / "chapters.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
    (jdir / "book.md").write_text(chapters_to_markdown(chapters, book_title, book_author), encoding="utf-8")
    (jdir / "book.txt").write_text(chapters_to_plain(chapters), encoding="utf-8")
    _set_meta(job_id, chapters_total=len(chapters), chapters_done=0, manuscript_ready=True)

    if not generate_audio:
        update_job(
            job_id,
            status="done",
            stage="done",
            progress=100,
            message="Manuscript ready (no audio requested)",
            result_path=str(jdir / "book.md"),
        )
        return

    await _render_audiobook_audio(job_id, jdir, job, chapters, meta)


async def _render_audiobook_audio(
    job_id: str,
    jdir: Path,
    job: dict,
    chapters: list,
    meta: dict,
) -> None:
    voice_id = job.get("voice_id")
    lang = job.get("lang") or (chapters[0].get("language") if chapters else None) or meta.get("lang") or "en"
    ref_audio = None
    if voice_id:
        voice = get_voice(voice_id)
        if voice and voice.get("artifact_path"):
            ref = Path(voice["artifact_path"])
            if ref.is_file():
                ref_audio = ref
            elif (ref / "reference.wav").exists():
                ref_audio = ref / "reference.wav"

    audio_dir = jdir / "audio"
    audio_dir.mkdir(exist_ok=True)
    chapter_audio: list[Path] = []
    chapter_wavs: list[Path] = []
    total_chapters = len(chapters)

    for ci, chapter in enumerate(chapters):
        update_job(
            job_id,
            stage=f"tts_chapter_{ci + 1}",
            progress=50 + (ci / max(total_chapters, 1)) * 40,
            message=f"TTS chapter {ci + 1}/{total_chapters}: {chapter['title']}",
        )
        chunk_files: list[Path] = []
        for pi, chunk in enumerate(chapter.get("chunks") or [chapter["content"]]):
            chunk_base = audio_dir / f"chapter_{ci + 1:03d}_part_{pi + 1:03d}"
            chunk_path = await synthesize(
                chunk, chunk_base.with_suffix(".wav"), voice_id=voice_id, lang=lang, ref_audio=ref_audio
            )
            chunk_files.append(chunk_path)

        chapter_mp3 = audio_dir / f"chapter_{ci + 1:03d}.mp3"
        concat_audio(chunk_files, chapter_mp3)
        chapter_audio.append(chapter_mp3)
        chapter_wavs.append(chapter_mp3)
        _set_meta(job_id, chapters_done=ci + 1)

    update_job(job_id, stage="muxing", progress=92, message="Packaging audiobook")
    result = package_audiobook(jdir, chapters, chapter_audio, chapter_wavs=chapter_wavs)
    label_job_chapters(jdir, voice_id)
    cleanup_job_artifacts(jdir)
    write_job_readme(job_id)
    eng = engine_label()
    if voice_id and eng == "xtts":
        voice_note = " (your voice via XTTS)"
    elif voice_id and eng == "edge":
        voice_note = " (voice sample saved — clone engine not installed, used Edge preview)"
    elif voice_id:
        voice_note = f" (voice linked — {eng})"
    else:
        voice_note = ""
    update_job(
        job_id,
        status="done",
        stage="done",
        progress=100,
        message=f"Audiobook ready{voice_note}",
        result_path=str(result),
    )


async def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    if job["status"] in ("done", "failed"):
        return False
    update_job(job_id, status="cancelled", message="Cancelled by user")
    return True
