"""Human-readable labels inside opaque job-id folders."""

import json
import re
from pathlib import Path

from db import get_job, job_dir, list_jobs
from services.book_metadata import display_name


def _safe_name(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:max_len] or "book"


def write_job_readme(job_id: str) -> Path:
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    jdir = job_dir(job_id)
    meta = json.loads(job.get("meta_json") or "{}")
    title = meta.get("title") or job_id
    author = meta.get("author") or ""
    lines = [
        "CATTS audiobook job",
        "===================",
        f"Title:  {title}",
    ]
    if author:
        lines.append(f"Author: {author}")
    lines.extend([
        f"ID:     {job_id}",
        f"Status: {job.get('status')} — {job.get('message', '')}",
        "",
        "Main files:",
        "  book.md / book.txt     polished manuscript",
        "  audiobook.m4b          full audiobook (or audiobook.zip)",
        "  audio/chapter_*.mp3    one file per chapter",
        "  audio/{Voice}_{EN|ES}_chapter_*.mp3   labeled copies (voice name in filename)",
        "",
        "Open this folder from the GUI: Books → Open folder",
    ])
    readme = jdir / "README.txt"
    readme.write_text("\n".join(lines), encoding="utf-8")
    (jdir / "TITLE.txt").write_text(display_name(title, author), encoding="utf-8")
    return readme


def backfill_all_readmes() -> int:
    count = 0
    for job in list_jobs(500):
        jdir = job_dir(job["id"])
        if jdir.exists():
            write_job_readme(job["id"])
            count += 1
    return count
