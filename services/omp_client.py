"""Spawn omp (Oh My Pi) and parse --mode json output."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from config import BASE_DIR, OMP_BIN, OMP_CWD, OMP_MODEL, OMP_TIMEOUT_SEC

logger = logging.getLogger(__name__)

_LM_BASE = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:42/v1")
_TOKEN_FILE = Path.home() / ".secrets" / "lm-api-token"


def resolve_omp_bin() -> str | None:
    if OMP_BIN and Path(OMP_BIN).is_file():
        return OMP_BIN
    found = shutil.which("omp")
    if found:
        return found
    bun = Path.home() / ".bun" / "bin" / "omp.exe"
    return str(bun) if bun.is_file() else None


def token_configured() -> bool:
    if os.getenv("LM_STUDIO_API_KEY") or os.getenv("LM_API_KEY"):
        return True
    return _TOKEN_FILE.is_file() and bool(_TOKEN_FILE.read_text(encoding="utf-8").strip())


def _omp_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    token = (os.getenv("LM_STUDIO_API_KEY") or os.getenv("LM_API_KEY") or "").strip()
    if not token and _TOKEN_FILE.is_file():
        token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
    if token:
        env["LM_STUDIO_API_KEY"] = token
        env["LM_API_KEY"] = token
    env.setdefault("LM_STUDIO_BASE_URL", _LM_BASE)
    env.setdefault("LM_BASE_URL", _LM_BASE)
    return env


def _build_cmd(
    prompt: str,
    *,
    model: str | None = None,
    cwd: str | None = None,
    auto_approve: bool = True,
) -> list[str]:
    omp = resolve_omp_bin()
    if not omp:
        raise RuntimeError("omp not found — install Oh My Pi or set CATTS_OMP_BIN")
    cmd = [
        omp,
        "-p",
        "--mode",
        "json",
        "--model",
        model or OMP_MODEL,
        "--cwd",
        cwd or OMP_CWD,
    ]
    if auto_approve:
        cmd.append("--auto-approve")
    cmd.append(prompt)
    return cmd


def _parse_events(raw: str) -> tuple[list[dict[str, Any]], str, str | None]:
    events: list[dict[str, Any]] = []
    texts: list[str] = []
    session_id: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(ev)
        if ev.get("type") == "session" and ev.get("id"):
            session_id = ev["id"]
        msg = ev.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        if ev.get("type") not in ("message_end", "message"):
            continue
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
    return events, "\n".join(texts).strip(), session_id


async def omp_status() -> dict[str, Any]:
    omp = resolve_omp_bin()
    out: dict[str, Any] = {
        "omp_bin": omp,
        "omp_ready": bool(omp),
        "model_default": OMP_MODEL,
        "cwd_default": OMP_CWD,
        "token_configured": token_configured(),
        "lm_studio_base_url": _LM_BASE,
        "lm_studio_reachable": False,
        "lm_studio_models": [],
    }
    if not omp:
        return out
    try:
        proc = await asyncio.create_subprocess_exec(
            omp, "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        help_out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        first = (help_out or b"").decode("utf-8", errors="replace").splitlines()
        if first:
            out["omp_version"] = first[0].strip()
    except Exception as exc:
        out["omp_version_error"] = str(exc)

    if token_configured():
        try:
            token = _omp_env().get("LM_STUDIO_API_KEY", "")
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    f"{_LM_BASE.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {token}"},
                )
                r.raise_for_status()
                data = r.json().get("data") or []
                out["lm_studio_reachable"] = True
                out["lm_studio_models"] = [m.get("id") for m in data if m.get("id")]
        except Exception as exc:
            out["lm_studio_error"] = str(exc)
    return out


async def run_prompt(
    prompt: str,
    *,
    model: str | None = None,
    cwd: str | None = None,
    auto_approve: bool = True,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    cmd = _build_cmd(prompt, model=model, cwd=cwd, auto_approve=auto_approve)
    timeout = timeout_sec or OMP_TIMEOUT_SEC
    logger.info("omp: %s", " ".join(cmd[:-1]) + " <prompt>")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or OMP_CWD,
        env=_omp_env(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"omp timed out after {timeout}s") from None

    raw = (stdout or b"").decode("utf-8", errors="replace")
    err = (stderr or b"").decode("utf-8", errors="replace").strip()
    events, text, session_id = _parse_events(raw)
    ok = proc.returncode == 0
    if not ok and not text:
        raise RuntimeError(err or raw[-2000:] or f"omp exited {proc.returncode}")
    return {
        "ok": ok,
        "text": text,
        "session_id": session_id,
        "exit_code": proc.returncode,
        "stderr": err or None,
        "event_count": len(events),
    }


async def stream_prompt(
    prompt: str,
    *,
    model: str | None = None,
    cwd: str | None = None,
    auto_approve: bool = True,
) -> AsyncIterator[str]:
    cmd = _build_cmd(prompt, model=model, cwd=cwd, auto_approve=auto_approve)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or OMP_CWD,
        env=_omp_env(),
    )
    assert proc.stdout is not None
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace")
    finally:
        if proc.returncode is None:
            await proc.wait()
        if proc.stderr:
            err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            if err:
                yield json.dumps({"type": "omp_stderr", "text": err}) + "\n"
