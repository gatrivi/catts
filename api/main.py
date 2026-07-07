"""CATTS FastAPI application."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import agent, diagnostics, health, jobs, links, liteui, ocr, stt, voices
from config import API_HOST, API_PORT
from db import init_db
from services.job_manifest import backfill_all_readmes
from services.voice_fixup import fix_legacy_voice_names
from services.voice_labels import sync_all_voice_labels, backfill_all_job_labels
from services.stt_client import warmup_worker as stt_warmup
from services.xtts_tts import warmup_worker as xtts_warmup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        n = backfill_all_readmes()
        if n:
            logging.info("Wrote README.txt for %d job folders", n)
        v = fix_legacy_voice_names()
        if v:
            logging.info("Fixed %d legacy voice names", v)
        vl = sync_all_voice_labels()
        if vl:
            logging.info("Synced labeled files for %d voices", vl)
        jl = backfill_all_job_labels()
        if jl:
            logging.info("Labeled audio files for %d jobs", jl)
    except Exception:
        logging.exception("Startup backfill failed")
    threading.Thread(target=xtts_warmup, daemon=True, name="xtts-warmup").start()
    threading.Thread(target=stt_warmup, daemon=True, name="stt-warmup").start()
    yield


app = FastAPI(title="CATTS", description="PDF/EPUB/DOCX to Audiobook + Voice API", version="0.7.2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(agent.router)
app.include_router(jobs.router)
app.include_router(voices.router)
app.include_router(stt.router)
app.include_router(ocr.router)
app.include_router(diagnostics.router)
app.include_router(links.router)
app.include_router(liteui.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def gui():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return {"message": "CATTS API running — open /docs"}


def run():
    import uvicorn

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=False)


if __name__ == "__main__":
    run()
