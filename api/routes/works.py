"""AudioManifest v1 prayer/devotion library (pre-generated)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.deps import require_api_key
from config import DATA_DIR

router = APIRouter(prefix="/works", tags=["works"])

WORKS_ROOT = DATA_DIR / "audio_works"
AUDIO_ROOT = WORKS_ROOT / "audio"


def _public_src(rel: str) -> str:
    rel = (rel or "").lstrip("/")
    return f"/works-files/{rel}"


def _load_manifest(work_id: str) -> dict:
    path = AUDIO_ROOT / work_id / "manifest.json"
    if not path.is_file():
        raise HTTPException(404, f"work not found: {work_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for asset in data.get("assets") or []:
        if "src" in asset:
            asset["src"] = _public_src(asset["src"])
        timings = asset.get("timings") or {}
        if timings.get("json"):
            timings["json"] = _public_src(timings["json"])
        if timings.get("vtt"):
            timings["vtt"] = _public_src(timings["vtt"])
        asset["timings"] = timings or None
    return data


@router.get("")
def list_works():
    """Public read — local prayer library for SPA play."""
    if not AUDIO_ROOT.is_dir():
        return {"works": []}
    works = []
    for d in sorted(AUDIO_ROOT.iterdir()):
        if not d.is_dir():
            continue
        man = d / "manifest.json"
        if not man.is_file():
            continue
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        w = data.get("work") or {}
        works.append(
            {
                "id": w.get("id") or d.name,
                "title": w.get("title") or d.name,
                "kind": w.get("kind"),
                "language": w.get("language"),
                "revision": w.get("revision"),
                "assetCount": len(data.get("assets") or []),
                "chapterCount": len(data.get("chapters") or []),
                "manifestUrl": f"/works/{d.name}",
            }
        )
    return {"works": works}


@router.get("/{work_id}")
def get_work(work_id: str):
    """Public read — manifest with /works-files URLs."""
    return _load_manifest(work_id)


@router.get("/{work_id}/file/{file_name}")
def get_work_file(work_id: str, file_name: str, _: None = Depends(require_api_key)):
    """Fallback file fetch (prefer /works-files static mount)."""
    if "/" in file_name or ".." in file_name:
        raise HTTPException(400, "invalid file name")
    path = AUDIO_ROOT / work_id / file_name
    if not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path)
