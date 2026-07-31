"""Chaptered audiobook library for CatReader / external apps."""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from api.deps import require_api_key
from config import BASE_DIR

router = APIRouter(prefix="/books", tags=["books"])

# Album roots to scan (first match wins per book id)
_LIBRARY_GLOBS = [
    BASE_DIR / "books" / "abogen" / "out",
]

_TRACK_RE = re.compile(r"^(\d{2})_(.+)\.(mp3|srt)$", re.I)


def _album_dirs() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for root in _LIBRARY_GLOBS:
        if not root.is_dir():
            continue
        for album in root.glob("*/album"):
            if not album.is_dir():
                continue
            book_dir = album.parent
            book_id = book_dir.name
            # prefer KEEP_ prefix as stable id slug
            found.append((book_id, album))
    return found


def _parse_tracks(album: Path) -> list[dict]:
    by_idx: dict[int, dict] = {}
    for p in album.iterdir():
        if not p.is_file():
            continue
        m = _TRACK_RE.match(p.name)
        if not m:
            continue
        idx = int(m.group(1))
        title = m.group(2).replace("_", " ").strip()
        ext = m.group(3).lower()
        slot = by_idx.setdefault(idx, {"index": idx, "title": title})
        if ext == "mp3":
            slot["audio"] = p
            # title from mp3 stem preferred
            slot["title"] = title
        elif ext == "srt":
            slot["subtitle"] = p
    tracks = []
    for idx in sorted(by_idx):
        slot = by_idx[idx]
        audio: Path | None = slot.get("audio")
        if not audio or not audio.is_file():
            continue
        empty_marker = album / f"{audio.stem}.EMPTY.txt"
        size = audio.stat().st_size
        # factually empty: marker or tiny file (<30KB ~ title only)
        empty = empty_marker.is_file() or size < 30_000
        sub = slot.get("subtitle")
        tracks.append(
            {
                "index": idx,
                "title": slot["title"],
                "empty": empty,
                "bytes": size,
                "audio_url": f"/books/{album.parent.name}/chapters/{idx}/audio",
                "subtitle_url": (
                    f"/books/{album.parent.name}/chapters/{idx}/subtitles"
                    if sub and Path(sub).is_file()
                    else None
                ),
            }
        )
    return tracks


def _book_meta(book_id: str, album: Path) -> dict:
    tracks = _parse_tracks(album)
    ready_n = sum(1 for t in tracks if not t["empty"])
    return {
        "id": book_id,
        "title": book_id.replace("KEEP_", "").replace("_", " ").strip(),
        "album_path": str(album),
        "chapters": len(tracks),
        "chapters_ready": ready_n,
        "chapters_empty": len(tracks) - ready_n,
        "ready": bool(tracks) and ready_n == len(tracks) and len(tracks) >= 1,
        "has_subtitles": all(t.get("subtitle_url") for t in tracks),
    }


def _resolve_album(book_id: str) -> Path:
    for bid, album in _album_dirs():
        if bid == book_id:
            return album
    raise HTTPException(404, f"Unknown book '{book_id}'")


def _resolve_chapter_file(book_id: str, chapter_index: int, kind: str) -> Path:
    album = _resolve_album(book_id)
    tracks = {t["index"]: t for t in _parse_tracks(album)}
    if chapter_index not in tracks:
        raise HTTPException(404, f"Chapter {chapter_index} not found")
    # map back to disk via glob
    prefix = f"{chapter_index:02d}_"
    if kind == "audio":
        matches = list(album.glob(f"{prefix}*.mp3"))
        media = "audio/mpeg"
    else:
        matches = list(album.glob(f"{prefix}*.srt"))
        media = "application/x-subrip"
    if not matches:
        raise HTTPException(404, f"No {kind} for chapter {chapter_index}")
    return matches[0]


@router.get("")
async def list_books(_: None = Depends(require_api_key)):
    """List chaptered audiobooks (album folders with mp3+srt)."""
    books = [_book_meta(bid, album) for bid, album in _album_dirs()]
    books.sort(key=lambda b: b["id"])
    return {"books": books}


@router.get("/{book_id}")
async def get_book(book_id: str, _: None = Depends(require_api_key)):
    album = _resolve_album(book_id)
    meta = _book_meta(book_id, album)
    meta["chapters_detail"] = _parse_tracks(album)
    # strip Path objects if any leaked — already dicts
    return meta


@router.get("/{book_id}/download")
async def download_book_zip(
    book_id: str,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
):
    """Zip of ready chapter mp3s (STORE — already compressed)."""
    album = _resolve_album(book_id)
    tracks = [t for t in _parse_tracks(album) if not t["empty"]]
    if not tracks:
        raise HTTPException(404, f"No ready audio for '{book_id}'")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_STORED) as zf:
            for t in tracks:
                mp3 = _resolve_chapter_file(book_id, int(t["index"]), "audio")
                zf.write(mp3, arcname=mp3.name)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    def _cleanup() -> None:
        tmp_path.unlink(missing_ok=True)

    background_tasks.add_task(_cleanup)
    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename=f"{book_id}.zip",
        content_disposition_type="attachment",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{book_id}/chapters/{chapter_index}/audio")
async def get_chapter_audio(book_id: str, chapter_index: int, _: None = Depends(require_api_key)):
    path = _resolve_chapter_file(book_id, chapter_index, "audio")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=path.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{book_id}/chapters/{chapter_index}/subtitles")
async def get_chapter_subtitles(book_id: str, chapter_index: int, _: None = Depends(require_api_key)):
    path = _resolve_chapter_file(book_id, chapter_index, "subtitles")
    return FileResponse(
        path,
        media_type="application/x-subrip",
        filename=path.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )
