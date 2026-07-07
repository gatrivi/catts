from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import require_api_key

router = APIRouter(prefix="/liteui", tags=["liteui"])

_BASE_DIR = Path(__file__).resolve().parents[2]
_LITEUI_DIR = _BASE_DIR / "external" / "LiteUI-Studio"
_START_SCRIPT = _LITEUI_DIR / "start_en.py"
_EMBEDDED_PYTHON = _LITEUI_DIR / "python" / "python.exe"

LITEUI_BACKEND_PORT = 8188
LITEUI_UI_PORT = 7860
LITEUI_HOST = "127.0.0.1"

_proc_lock = threading.Lock()
_proc: subprocess.Popen | None = None


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.8)
        return s.connect_ex((LITEUI_HOST, port)) == 0


def _ui_url() -> str:
    return f"http://{LITEUI_HOST}:{LITEUI_UI_PORT}/"


def _backend_url() -> str:
    return f"http://{LITEUI_HOST}:{LITEUI_BACKEND_PORT}/"


class LiteUIStatus(BaseModel):
    running: bool
    backend_port_open: bool
    ui_port_open: bool
    ui_url: str
    backend_url: str
    embedded_python_ok: bool
    start_script_ok: bool
    error: str | None = None
    state: Literal["stopped", "starting", "running"]


class LiteUIStartResponse(BaseModel):
    started: bool
    starting: bool
    state: LiteUIStatus["state"]
    ui_url: str
    message: str


@router.get("/status", response_model=LiteUIStatus)
async def liteui_status(_: None = Depends(require_api_key)) -> LiteUIStatus:
    ui_open = _port_open(LITEUI_UI_PORT)
    be_open = _port_open(LITEUI_BACKEND_PORT)
    embedded_ok = _EMBEDDED_PYTHON.is_file()
    start_ok = _START_SCRIPT.is_file()

    running = ui_open
    state: LiteUIStatus["state"] = "running" if running else "stopped"
    err: str | None = None
    if not start_ok:
        err = f"Missing start script at {str(_START_SCRIPT)}"
    elif not embedded_ok:
        err = (
            "LiteUI embedded python not found. You must unzip the provided `python.zip` "
            "into the LiteUI-Studio repo (creates `python/python.exe`)."
        )

    # If a process exists but ports aren’t open yet, we treat it as "starting".
    global _proc
    with _proc_lock:
        if _proc is not None and _proc.poll() is None and not running:
            state = "starting"
            err = err or "Process spawned; waiting for ports to open."

    return LiteUIStatus(
        running=running,
        backend_port_open=be_open,
        ui_port_open=ui_open,
        ui_url=_ui_url(),
        backend_url=_backend_url(),
        embedded_python_ok=embedded_ok,
        start_script_ok=start_ok,
        error=err,
        state=state,
    )


@router.post("/start", response_model=LiteUIStartResponse)
async def liteui_start(_: None = Depends(require_api_key)) -> LiteUIStartResponse:
    st = await liteui_status()
    if st.running:
        return LiteUIStartResponse(
            started=False,
            starting=False,
            state="running",
            ui_url=st.ui_url,
            message="LiteUI already running.",
        )
    if st.embedded_python_ok is False or st.start_script_ok is False:
        raise HTTPException(412, st.error or "LiteUI not ready.")

    global _proc
    with _proc_lock:
        if _proc is not None and _proc.poll() is None:
            return LiteUIStartResponse(
                started=False,
                starting=True,
                state="starting",
                ui_url=_ui_url(),
                message="LiteUI startup already in progress.",
            )

        # We launch the wrapper script; it in turn spawns backend + Gradio UI.
        if not _START_SCRIPT.exists():
            raise HTTPException(412, f"Missing start script: {_START_SCRIPT}")
        if not _EMBEDDED_PYTHON.exists():
            raise HTTPException(412, f"Missing embedded python: {_EMBEDDED_PYTHON}")

        _proc = subprocess.Popen(
            [sys.executable, str(_START_SCRIPT)],
            cwd=str(_LITEUI_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    return LiteUIStartResponse(
        started=True,
        starting=True,
        state="starting",
        ui_url=_ui_url(),
        message="LiteUI start requested; wait until ports open.",
    )

