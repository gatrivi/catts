import os
import time
from pathlib import Path

import httpx


CATTS_API_BASE = os.getenv("CATTS_API_BASE", "http://127.0.0.1:59200").rstrip("/")


def _pick_title(pdf_path: Path) -> str:
    # Keep it simple: filename without extension.
    return pdf_path.stem


def _human_status(job: dict) -> str:
    return f"status={job.get('status')} stage={job.get('stage')} progress={job.get('progress')}"


def main() -> int:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python upload_audiobook_from_pdf.py <pdf_path>")

    pdf_path = Path(sys.argv[1]).expanduser()
    if not pdf_path.exists():
        raise SystemExit(f"Missing file: {pdf_path}")

    url = f"{CATTS_API_BASE}/jobs/audiobook"
    title = _pick_title(pdf_path)

    # Kokoro mode does not require voice cloning; we still let CATTS pick a default voice.
    data = {
        "lang": os.getenv("CATTS_BOOK_LANG", "en"),
        "title": title,
        "author": os.getenv("CATTS_BOOK_AUTHOR", ""),
        "chapter_mode": os.getenv("CATTS_CHAPTER_MODE", "detect_number"),
        "generate_audio": os.getenv("CATTS_GENERATE_AUDIO", "true"),
    }

    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = httpx.post(url, data=data, files=files, timeout=120)

    r.raise_for_status()
    j = r.json()
    job_id = j["job_id"]
    print(f"JOB_ID={job_id}")

    # Poll until done/failed/cancelled.
    job_url = f"{CATTS_API_BASE}/jobs/{job_id}"
    deadline_s = int(os.getenv("CATTS_POLL_DEADLINE_S", "900"))  # default ~15 min
    t0 = time.time()

    with httpx.Client(timeout=30) as client:
        while True:
            if time.time() - t0 > deadline_s:
                print("TIMEOUT waiting for job; check UI for status.")
                return 2

            jr = client.get(job_url)
            if jr.status_code != 200:
                print(f"JOB_POLL_HTTP={jr.status_code} body={jr.text[:200]}")
                time.sleep(5)
                continue

            job = jr.json()
            status = job.get("status")
            stage = job.get("stage")
            progress = job.get("progress")
            print(f"POLL {_human_status(job)}")

            if status in ("done", "failed", "cancelled"):
                if status != "done":
                    print(f"JOB_ERROR={job.get('error') or job.get('message')}")
                return 0 if status == "done" else 1

            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())

