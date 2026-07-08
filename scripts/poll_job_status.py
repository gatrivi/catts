import os
import time
from typing import Any

import httpx


CATTS_API_BASE = os.getenv("CATTS_API_BASE", "http://127.0.0.1:59200").rstrip("/")


def main() -> int:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python poll_job_status.py <job_id>")

    job_id = sys.argv[1].strip()
    job_url = f"{CATTS_API_BASE}/jobs/{job_id}"
    deadline_s = int(os.getenv("CATTS_POLL_DEADLINE_S", "1800"))  # 30 min default
    t0 = time.time()

    with httpx.Client(timeout=30) as client:
        while True:
            if time.time() - t0 > deadline_s:
                print("TIMEOUT")
                return 2

            try:
                r = client.get(job_url)
                r.raise_for_status()
                job: dict[str, Any] = r.json()
            except Exception as e:
                print(f"poll_error: {e}")
                time.sleep(5)
                continue

            status = job.get("status")
            stage = job.get("stage")
            progress = job.get("progress")
            print(f"POLL status={status} stage={stage} progress={progress}")

            if status in ("done", "failed", "cancelled"):
                if status != "done":
                    print("JOB_ERROR=" + str(job.get("error") or job.get("message") or ""))
                return 0 if status == "done" else 1

            time.sleep(8)


if __name__ == "__main__":
    raise SystemExit(main())

