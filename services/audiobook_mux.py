"""Audiobook packaging: concat chapter WAVs into zip or m4b."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def concat_audio(files: list[Path], output: Path) -> Path:
    """Concatenate audio files (wav/mp3) via ffmpeg."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if not files:
        raise ValueError("No audio files to concat")
    if len(files) == 1:
        shutil.copy(files[0], output)
        return output
    if not _ffmpeg_available():
        shutil.copy(files[0], output)
        return output

    list_file = output.parent / "concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in files), encoding="utf-8")
    ext = output.suffix.lower()
    codec = "copy" if all(f.suffix.lower() == ext for f in files) else "aac"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file)]
    if codec == "copy":
        cmd += ["-c", "copy", str(output)]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k", str(output)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output


def concat_wavs(wav_files: list[Path], output: Path) -> Path:
    return concat_audio(wav_files, output)


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> Path:
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    if not _ffmpeg_available():
        shutil.copy(wav_path, mp3_path.with_suffix(".wav"))
        return mp3_path.with_suffix(".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)],
        check=True,
        capture_output=True,
    )
    return mp3_path


def build_zip(job_dir: Path, chapters: list[dict], chapter_audio: list[Path]) -> Path:
    out_zip = job_dir / "audiobook.zip"
    metadata = {
        "chapters": [
            {"index": i + 1, "title": ch.get("title", f"Chapter {i + 1}"), "audio": chapter_audio[i].name}
            for i, ch in enumerate(chapters)
            if i < len(chapter_audio)
        ]
    }
    (job_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(job_dir / "metadata.json", "metadata.json")
        for audio in chapter_audio:
            zf.write(audio, audio.name)
    return out_zip


def _audio_duration_ms(path: Path) -> int:
    if path.suffix.lower() == ".wav":
        import wave

        with wave.open(str(path), "r") as wf:
            return int(wf.getnframes() / wf.getframerate() * 1000)
    if shutil.which("ffprobe"):
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(float(result.stdout.strip()) * 1000)
    return 60_000


def build_m4b(job_dir: Path, chapters: list[dict], chapter_files: list[Path]) -> Path | None:
    if not _ffmpeg_available() or not chapter_files:
        return None

    combined = job_dir / "combined.m4a"
    concat_audio(chapter_files, combined)
    out_m4b = job_dir / "audiobook.m4b"

    meta_file = job_dir / "ffmetadata.txt"
    lines = [";FFMETADATA1"]
    offset_ms = 0
    for ch, audio in zip(chapters, chapter_files):
        duration_ms = _audio_duration_ms(audio)
        title = ch["title"].replace("=", "\\=")
        lines.extend([
            "[CHAPTER]", "TIMEBASE=1/1000",
            f"START={offset_ms}", f"END={offset_ms + duration_ms}",
            f"title={title}",
        ])
        offset_ms += duration_ms
    meta_file.write_text("\n".join(lines), encoding="utf-8")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(combined), "-i", str(meta_file),
            "-map_metadata", "1", "-c:a", "aac", "-b:a", "128k", str(out_m4b),
        ],
        check=True,
        capture_output=True,
    )
    return out_m4b


def package_audiobook(
    job_dir: Path,
    chapters: list[dict],
    chapter_audio: list[Path],
    chapter_wavs: list[Path] | None = None,
    prefer_m4b: bool = True,
) -> Path:
    build_zip(job_dir, chapters, chapter_audio)
    tracks = chapter_audio or chapter_wavs or []
    if prefer_m4b:
        m4b = build_m4b(job_dir, chapters, tracks)
        if m4b:
            return m4b
    return job_dir / "audiobook.zip"
