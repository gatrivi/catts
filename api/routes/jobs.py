import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.deps import require_api_key
from api.schemas import JobFiles, JobMetadataPatch, JobProgress, JobStatus, JobSummary
from db import create_job, delete_job, get_job, job_dir, list_jobs, update_job
from services.book_metadata import display_name, guess_metadata_from_filename
from services.job_manifest import backfill_all_readmes, write_job_readme
from services.job_runner import cancel_job, enqueue_audiobook
from services.job_regenerate import regenerate_job_audio
from services.reveal import reveal_in_folder
from services.voice_default import resolve_default_voice_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_meta(job: dict) -> dict:
    return json.loads(job.get("meta_json") or "{}")


def _job_display(job: dict) -> str:
    m = _job_meta(job)
    return display_name(m.get("title"), m.get("author"))


def _job_response(job: dict) -> JobProgress:
    meta = _job_meta(job)
    return JobProgress(
        id=job["id"],
        kind=job["kind"],
        status=JobStatus(job["status"]),
        stage=job.get("stage") or "",
        progress=float(job.get("progress") or 0),
        message=job.get("message") or "",
        voice_id=job.get("voice_id"),
        lang=job.get("lang"),
        title=meta.get("title"),
        author=meta.get("author"),
        display_name=_job_display(job),
        chapters_done=meta.get("chapters_done"),
        chapters_total=meta.get("chapters_total"),
        manuscript_ready=bool(meta.get("manuscript_ready")),
        result_ready=job["status"] == "done" and bool(job.get("result_path")),
        error=job.get("error"),
    )


@router.get("", response_model=list[JobSummary])
async def list_all_jobs(limit: int = 50, _: None = Depends(require_api_key)):
    return [
        JobSummary(
            id=j["id"],
            status=JobStatus(j["status"]),
            stage=j.get("stage") or "",
            progress=float(j.get("progress") or 0),
            message=j.get("message") or "",
            title=json.loads(j.get("meta_json") or "{}").get("title"),
            author=json.loads(j.get("meta_json") or "{}").get("author"),
            display_name=_job_display(j),
            created_at=j.get("created_at"),
            error=j.get("error"),
            result_ready=j["status"] == "done" and bool(j.get("result_path")),
        )
        for j in list_jobs(limit)
    ]


@router.get("/parse-filename")
async def parse_filename(name: str):
    return guess_metadata_from_filename(name)


@router.post("/audiobook")
async def create_audiobook_job(
    voice_id: str | None = Form(None),
    lang: str | None = Form(None),
    title: str | None = Form(None),
    author: str | None = Form(None),
    chapter_mode: str = Form("detect"),
    callback_url: str | None = Form(None),
    generate_audio: str = Form("true"),
    file: UploadFile | None = File(None),
    pdf: UploadFile | None = File(None),
    epub: UploadFile | None = File(None),
    text: UploadFile | None = File(None),
    _: None = Depends(require_api_key),
):
    upload = file or pdf or epub or text
    if not upload:
        raise HTTPException(400, "Upload pdf, epub, or text file")

    guessed = guess_metadata_from_filename(upload.filename or "book.pdf")
    meta = {
        "title": (title or guessed["title"] or upload.filename or "Audiobook").strip(),
        "author": (author or guessed.get("author") or "").strip(),
        "chapter_mode": chapter_mode if chapter_mode in ("detect", "number", "detect_number") else "detect",
        "generate_audio": generate_audio.lower() not in ("false", "0", "no"),
        "lang": lang,
    }
    job_id = create_job(
        "audiobook",
        voice_id=voice_id or resolve_default_voice_id(),
        lang=lang,
        callback_url=callback_url,
        meta=meta,
    )
    jdir = job_dir(job_id)

    fname = (upload.filename or "").lower()
    if fname.endswith(".pdf") or upload is pdf:
        dest = jdir / "input.pdf"
    elif fname.endswith(".epub") or upload is epub:
        dest = jdir / "input.epub"
    elif fname.endswith(".docx"):
        dest = jdir / "input.docx"
    else:
        dest = jdir / "input.txt"

    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    write_job_readme(job_id)
    await enqueue_audiobook(job_id)
    return {"job_id": job_id, "status": "queued", "title": meta["title"], "display_name": display_name(meta["title"], meta["author"])}


@router.patch("/{job_id}/metadata")
async def patch_job_metadata(
    job_id: str,
    body: JobMetadataPatch,
    _: None = Depends(require_api_key),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    meta = _job_meta(job)
    if body.title is not None:
        meta["title"] = body.title.strip()
    if body.author is not None:
        meta["author"] = body.author.strip()
    if body.chapter_mode is not None:
        meta["chapter_mode"] = body.chapter_mode
    update_job(job_id, meta=meta)
    write_job_readme(job_id)
    return {"display_name": display_name(meta.get("title"), meta.get("author")), "meta": meta}


@router.post("/cleanup-all")
async def cleanup_all_jobs(_: None = Depends(require_api_key)):
    total_removed = 0
    total_freed = 0
    jobs = list_jobs(500)
    for job in jobs:
        if job["status"] == "done":
            stats = cleanup_job_artifacts(job_dir(job["id"]), force=True)
            total_removed += stats.get("removed", 0)
            total_freed += stats.get("freed_bytes", 0)
            write_job_readme(job["id"])
    return {"jobs": len(jobs), "removed": total_removed, "freed_bytes": total_freed}


@router.get("/{job_id}", response_model=JobProgress)
async def get_job_status(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@router.get("/{job_id}/manuscript")
async def get_manuscript(job_id: str, format: str = "md", _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    jdir = job_dir(job_id)
    if format == "txt":
        path = jdir / "book.txt"
        media = "text/plain"
    else:
        path = jdir / "book.md"
        media = "text/markdown"
    if not path.exists():
        raise HTTPException(404, "Manuscript not ready yet")
    return FileResponse(path, media_type=media, filename=path.name)


@router.get("/{job_id}/result")
async def get_job_result(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "done":
        raise HTTPException(409, f"Job not ready (status={job['status']})")
    result = job.get("result_path")
    if not result or not Path(result).exists():
        raise HTTPException(404, "Result file missing")
    path = Path(result)
    if path.suffix == ".m4b":
        media = "audio/mp4"
    elif path.suffix == ".zip":
        media = "application/zip"
    elif path.suffix == ".md":
        media = "text/markdown"
    else:
        media = "application/octet-stream"
    return FileResponse(path, media_type=media, filename=path.name)


@router.get("/{job_id}/files", response_model=JobFiles)
async def get_job_files(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    jdir = job_dir(job_id)
    result = job.get("result_path")
    result_path = Path(result) if result else None
    chapter_mp3s = sorted(
        p for p in jdir.glob("audio/chapter_*.mp3") if "_part_" not in p.name
    )
    chapter_meta = []
    chapters_json = jdir / "chapters.json"
    if chapters_json.exists():
        chapters = json.loads(chapters_json.read_text(encoding="utf-8"))
        for i, p in enumerate(chapter_mp3s):
            title = chapters[i]["title"] if i < len(chapters) else f"Chapter {i + 1}"
            chapter_meta.append({"index": i + 1, "file": p.name, "title": title})
    else:
        chapter_meta = [{"index": i + 1, "file": p.name, "title": f"Chapter {i + 1}"} for i, p in enumerate(chapter_mp3s)]
    md = jdir / "book.md"
    txt = jdir / "book.txt"
    playable = bool(result_path and result_path.exists() and result_path.suffix in (".m4b", ".mp3", ".wav"))
    return JobFiles(
        job_id=job_id,
        folder=str(jdir.resolve()),
        audiobook_path=str(result_path.resolve()) if result_path and result_path.exists() else None,
        audiobook_name=result_path.name if result_path and result_path.exists() else None,
        manuscript_md=str(md.resolve()) if md.exists() else None,
        manuscript_txt=str(txt.resolve()) if txt.exists() else None,
        chapters=chapter_meta,
        playable=playable,
    )


@router.post("/{job_id}/reveal")
async def reveal_job_folder(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    jdir = job_dir(job_id)
    if not jdir.exists():
        raise HTTPException(404, "Job folder missing")
    result = job.get("result_path")
    target = Path(result) if result and Path(result).exists() else jdir
    reveal_in_folder(target)
    return {"opened": str(target.resolve())}


@router.get("/{job_id}/chapters/{chapter_num}/audio")
async def get_chapter_audio(job_id: str, chapter_num: int, _: None = Depends(require_api_key)):
    jdir = job_dir(job_id)
    for ext in (".mp3", ".wav"):
        path = jdir / "audio" / f"chapter_{chapter_num:03d}{ext}"
        if path.exists():
            media = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            return FileResponse(path, media_type=media, filename=path.name)
    raise HTTPException(404, "Chapter audio not found")


@router.post("/{job_id}/cleanup")
async def cleanup_job(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    stats = cleanup_job_artifacts(job_dir(job_id), force=True)
    return stats


@router.post("/{job_id}/regenerate")
async def regenerate_audiobook(
    job_id: str,
    voice_id: str | None = Form(None),
    _: None = Depends(require_api_key),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] == "running":
        raise HTTPException(409, "Job is still running")
    try:
        await regenerate_job_audio(
            job_id,
            voice_id=voice_id or job.get("voice_id") or resolve_default_voice_id(),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"job_id": job_id, "status": "queued"}


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] not in ("failed", "cancelled"):
        raise HTTPException(409, "Only failed/cancelled jobs can be retried")
    update_job(job_id, status="queued", stage="uploaded", progress=0, message="Retrying", error=None)
    await enqueue_audiobook(job_id)
    return {"job_id": job_id, "status": "queued"}


@router.delete("/{job_id}")
async def delete_audiobook_job(job_id: str, _: None = Depends(require_api_key)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in ("queued", "running"):
        await cancel_job(job_id)
    delete_job(job_id)
    return {"deleted": True}
