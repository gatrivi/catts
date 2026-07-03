"""Human-readable filenames for voice samples and audiobook chapters."""

import json
import re
import shutil
from pathlib import Path

from db import get_voice, list_voices, voice_dir

LABELED_RE = re.compile(r"^.+_(EN|ES)_(sample|reference)\.\w+$", re.IGNORECASE)
BOOK_LABELED_RE = re.compile(r"^.+--ch\d+\.mp3$", re.IGNORECASE)
BOOK_M4B_RE = re.compile(r"^.+--audiobook\.m4b$", re.IGNORECASE)


def book_file_slug(title: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^\w\s-]", "", (title or "").strip(), flags=re.UNICODE)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")[:max_len]
    return slug or "book"


def voice_file_prefix(name: str, lang: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", (name or "").strip(), flags=re.UNICODE)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")[:40] or "voice"
    lang_tag = "ES" if (lang or "en").startswith("es") else "EN"
    return f"{slug}_{lang_tag}"


def _find_sample(vdir: Path) -> Path | None:
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".webm"):
        p = vdir / f"sample{ext}"
        if p.exists():
            return p
    return None


def _find_reference(vdir: Path) -> Path | None:
    ref = vdir / "reference.wav"
    return ref if ref.exists() else None


def _remove_old_labeled(vdir: Path, pattern: re.Pattern[str]) -> None:
    for p in vdir.iterdir():
        if p.is_file() and pattern.match(p.name):
            p.unlink(missing_ok=True)


def sync_voice_labeled_files(voice_id: str) -> dict[str, str]:
    voice = get_voice(voice_id)
    if not voice:
        return {}
    vdir = voice_dir(voice_id)
    if not vdir.exists():
        return {}

    prefix = voice_file_prefix(voice.get("name") or "", voice.get("lang") or "en")
    _remove_old_labeled(vdir, LABELED_RE)

    out: dict[str, str] = {}
    sample = _find_sample(vdir)
    if sample:
        dst = vdir / f"{prefix}_sample{sample.suffix.lower()}"
        shutil.copy2(sample, dst)
        out["sample"] = str(dst)

    reference = _find_reference(vdir)
    if reference:
        dst = vdir / f"{prefix}_reference{reference.suffix.lower()}"
        shutil.copy2(reference, dst)
        out["reference"] = str(dst)

    manifest = {
        "id": voice_id,
        "name": voice.get("name"),
        "lang": voice.get("lang"),
        "prefix": prefix,
        "labeled_files": {k: Path(v).name for k, v in out.items()},
        "canonical": {
            "sample": sample.name if sample else None,
            "reference": reference.name if reference else None,
        },
    }
    (vdir / "VOICE.txt").write_text(
        "\n".join(
            [
                "CATTS voice profile",
                "===================",
                f"Name:   {voice.get('name')}",
                f"Lang:   {voice.get('lang')}",
                f"ID:     {voice_id}",
                f"Status: {voice.get('status')}",
                "",
                "Labeled files (easy to spot in Explorer):",
                *(f"  {name}" for name in manifest["labeled_files"].values()),
                "",
                "Re-record: train a new voice with the same name, or delete this folder.",
            ]
        ),
        encoding="utf-8",
    )
    (vdir / "voice.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def label_job_chapters(job_dir: Path, voice_id: str | None) -> int:
    from db import get_job

    job_id = job_dir.name
    job = get_job(job_id)
    if not job:
        return 0

    meta = {}
    try:
        import json as _json

        meta = _json.loads(job.get("meta_json") or "{}")
    except Exception:
        pass

    title = meta.get("title") or job_id
    lang = job.get("lang") or meta.get("lang") or "en"
    book_slug = book_file_slug(title)
    lang_tag = "ES" if str(lang).startswith("es") else "EN"

    audio_dir = job_dir / "audio"
    if not audio_dir.exists():
        return 0

    voice_prefix = ""
    if voice_id:
        voice = get_voice(voice_id)
        if voice:
            voice_prefix = voice_file_prefix(voice.get("name") or "", voice.get("lang") or lang)

    base = f"{book_slug}_{lang_tag}"
    if voice_prefix:
        base = f"{book_slug}__{voice_prefix}"

    _remove_old_labeled(audio_dir, BOOK_LABELED_RE)
    for old in job_dir.iterdir():
        if old.is_file() and BOOK_M4B_RE.match(old.name):
            old.unlink(missing_ok=True)

    count = 0
    chapters_json = job_dir / "chapters.json"
    chapter_titles: list[str] = []
    if chapters_json.exists():
        try:
            import json as _json

            chapter_titles = [c.get("title", "") for c in _json.loads(chapters_json.read_text(encoding="utf-8"))]
        except Exception:
            pass

    for src in sorted(audio_dir.glob("chapter_*.mp3")):
        if "_part_" in src.name or BOOK_LABELED_RE.match(src.name):
            continue
        if src.stat().st_size < 4096:
            continue
        m = re.search(r"chapter_(\d+)", src.name)
        ch_num = int(m.group(1)) if m else count + 1
        ch_title = ""
        if 0 < ch_num <= len(chapter_titles):
            ch_title = book_file_slug(chapter_titles[ch_num - 1], 24)
        suffix = f"--ch{ch_num:02d}"
        if ch_title and ch_title.lower() not in ("chapter", "capitulo", "book"):
            suffix += f"_{ch_title}"
        dst = audio_dir / f"{base}{suffix}.mp3"
        shutil.copy2(src, dst)
        count += 1

    m4b = job_dir / "audiobook.m4b"
    if m4b.exists() and m4b.stat().st_size > 4096:
        shutil.copy2(m4b, job_dir / f"{book_slug}--audiobook.m4b")

    voice_line = ""
    if voice_id:
        voice = get_voice(voice_id)
        if voice:
            voice_line = f"{voice.get('name')} ({voice.get('lang')}) — id {voice_id}"

    readme_extra = [
        "",
        f"Book files: audio/{base}--ch*.mp3",
        f"           {book_slug}--audiobook.m4b (if generated)",
    ]
    if voice_line:
        readme_extra.insert(1, f"Voice:  {voice_line}")
    readme = job_dir / "README.txt"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if "Book files:" not in text:
            readme.write_text(text.rstrip() + "\n" + "\n".join(readme_extra) + "\n", encoding="utf-8")

    meta_path = job_dir / "metadata.json"
    if meta_path.exists():
        import json as _json

        meta_data = _json.loads(meta_path.read_text(encoding="utf-8"))
        meta_data["book_slug"] = book_slug
        meta_data["labeled_prefix"] = base
        if voice_id:
            meta_data["voice_id"] = voice_id
            if voice := get_voice(voice_id):
                meta_data["voice_name"] = voice.get("name")
        meta_path.write_text(_json.dumps(meta_data, indent=2), encoding="utf-8")

    return count


def backfill_all_job_labels() -> int:
    from db import list_jobs, job_dir

    n = 0
    for job in list_jobs(500):
        jdir = job_dir(job["id"])
        if jdir.exists() and label_job_chapters(jdir, job.get("voice_id")):
            n += 1
    return n


def sync_all_voice_labels() -> int:
    n = 0
    for voice in list_voices(500):
        if sync_voice_labeled_files(voice["id"]):
            n += 1
    return n
