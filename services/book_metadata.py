"""Book title/author parsing and chapter naming."""

import re
from pathlib import Path


def filename_to_words(filename: str) -> list[str]:
    base = Path(filename).stem
    base = re.sub(r"[_]+", " ", base)
    base = re.sub(r"[-]+", " ", base)
    base = re.sub(r"[.]+", " ", base)
    return [w for w in base.split() if w]


def guess_metadata_from_filename(filename: str) -> dict:
    """Guess title + author from filename tokens."""
    words = filename_to_words(filename)
    if not words:
        return {"title": "Untitled", "author": "", "words": []}

    if len(words) >= 4:
        author = " ".join(words[-2:])
        title = " ".join(words[:-2])
    elif len(words) == 3:
        author = words[-1]
        title = " ".join(words[:-1])
    elif len(words) == 2:
        title, author = words[0], words[1]
    else:
        title, author = words[0], ""

    return {
        "title": _prettify_title(title),
        "author": _prettify_title(author),
        "words": words,
    }


def _prettify_title(text: str) -> str:
    if not text:
        return ""
    # Keep acronyms like PDF uppercase; title-case ordinary words
    parts = []
    for word in text.split():
        if word.isupper() and len(word) <= 4:
            parts.append(word)
        else:
            parts.append(word[:1].upper() + word[1:])
    return " ".join(parts)


def display_name(title: str | None, author: str | None = None) -> str:
    title = (title or "").strip() or "Untitled"
    author = (author or "").strip()
    if author:
        return f"{title} — {author}"
    return title


def apply_chapter_naming(chapters: list[dict], mode: str = "detect", lang: str = "en") -> list[dict]:
    """
    Chapter naming modes:
    - detect: keep headers found in the document
    - number: Chapter 1 / Capítulo 1
    - detect_number: detected subtitle + sequential number prefix
    """
    label = "Capítulo" if lang.startswith("es") else "Chapter"
    out = []
    for i, ch in enumerate(chapters, start=1):
        raw = (ch.get("title") or "").strip() or "Introduction"
        subtitle = _extract_chapter_subtitle(raw)
        if mode == "number":
            title = f"{label} {i}"
            if subtitle and subtitle.lower() not in title.lower():
                title = f"{title}: {subtitle}"
        elif mode == "detect_number":
            title = f"{label} {i}: {subtitle}" if subtitle else f"{label} {i}"
        else:
            title = raw if raw else f"{label} {i}"
        out.append({**ch, "title": title, "index": i, "slug": _slug(title)})
    return out


def _extract_chapter_subtitle(header: str) -> str:
    m = re.match(
        r"^(?:chapter|capítulo|capitulo|section|sección|seccion)\s+[\dIVXLCDM]+"
        r"\s*[:\-—–]\s*(.+)$",
        header,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    if header.lower() in ("introduction", "introducción", "introduccion", "full text"):
        return ""
    if re.match(r"^(?:chapter|capítulo|capitulo)\s+[\dIVXLCDM]+$", header, re.IGNORECASE):
        return ""
    return header


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip().lower())
    return s[:80] or "chapter"
