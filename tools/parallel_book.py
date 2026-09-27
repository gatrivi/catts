#!/usr/bin/env python3
"""Generate CatReader *.parallel.json files with local Argos Translate.

Designed for language study: source text is normalized and aligned sentence-by-sentence
(or line/paragraph-by-paragraph on request), then checkpointed so long books can resume.

Example (Windows, from catts):
  python tools/parallel_book.py ^
    "..\\catreader\\public\\books\\Rules_of_Christian_Decorum_and_Civility-La_Salle-1703_FR.txt" ^
    --source fr --target en --overwrite

By default the output sits next to the TXT using the CatReader convention:
  <book stem>.parallel.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable

LANG_TAGS = {
    "fr": "fr-FR",
    "en": "en-US",
    "es": "es-ES",
    "it": "it-IT",
    "de": "de-DE",
    "pt": "pt-BR",
}

SENTENCE_START = r"A-ZÀÂÄÆÇÉÈÊËÎÏÔÖŒÙÛÜŸ"


def clean_source(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # CatReader source note is provenance, not book content.
    lines = text.splitlines()
    if lines and (
        lines[0].startswith("Original French text")
        or lines[0].startswith("Public-domain")
        or lines[0].startswith("Project Gutenberg")
    ):
        lines = lines[1:]
    text = "\n".join(lines).strip()

    # PDF extraction often hyphenates words at visual line breaks.
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    # Remove isolated printed page numbers.
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)
    # Preserve paragraph boundaries, but unwrap visual line wrapping inside them.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n\n *", "\n\n", text)
    return text.strip()


def split_long(segment: str, max_chars: int = 520) -> list[str]:
    segment = segment.strip()
    if len(segment) <= max_chars:
        return [segment] if segment else []

    parts: list[str] = []
    remaining = segment
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        cut = max(
            window.rfind("; "),
            window.rfind(": "),
            window.rfind(", "),
            window.rfind(" "),
        )
        if cut < max_chars // 2:
            cut = max_chars
        else:
            cut += 1
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def segment_text(text: str, mode: str) -> list[str]:
    text = clean_source(text)
    if mode == "line":
        raw = [line.strip() for line in text.splitlines() if line.strip()]
    elif mode == "paragraph":
        raw = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    else:
        raw = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            # Keep short headings intact; split prose on sentence-ending punctuation.
            if len(paragraph) < 100 and not re.search(r"[.!?…]", paragraph):
                raw.append(paragraph)
                continue
            pieces = re.split(
                rf"(?<=[.!?…])\s+(?=[{SENTENCE_START}])",
                paragraph,
            )
            raw.extend(piece.strip() for piece in pieces if piece.strip())

    segments: list[str] = []
    for item in raw:
        segments.extend(split_long(item))
    return segments


def argos_translator(source_code: str, target_code: str) -> Callable[[str], str]:
    try:
        from argostranslate import translate as argos_translate
    except ImportError as exc:
        raise SystemExit(
            "Argos Translate is not installed in this Python environment. "
            "Activate the CatTS environment that already has Argos, or install argostranslate."
        ) from exc

    installed = argos_translate.get_installed_languages()
    source = next((lang for lang in installed if lang.code == source_code), None)
    target = next((lang for lang in installed if lang.code == target_code), None)
    if not source or not target:
        available = ", ".join(sorted({lang.code for lang in installed})) or "none"
        raise SystemExit(
            f"Missing installed Argos language package for {source_code}->{target_code}. "
            f"Installed languages: {available}"
        )

    try:
        translation = source.get_translation(target)
    except Exception as exc:  # Argos raises different types across versions.
        raise SystemExit(f"No installed Argos translation path {source_code}->{target_code}") from exc

    return translation.translate


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_checkpoint(
    output: Path,
    *,
    source_lang: str,
    target_lang: str,
    source_title: str,
    target_title: str,
    digest: str,
    mode: str,
    segments: list[dict],
) -> None:
    payload = {
        "version": 1,
        "sourceLanguage": LANG_TAGS.get(source_lang, source_lang),
        "targetLanguage": LANG_TAGS.get(target_lang, target_lang),
        "sourceTitle": source_title,
        "targetTitle": target_title,
        "generatedBy": "CatTS local Argos Translate",
        "sourceSha256": digest,
        "segmentation": mode,
        "segments": segments,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a CatReader bilingual parallel-book JSON file")
    parser.add_argument("input", type=Path, help="Source UTF-8 TXT book")
    parser.add_argument("--source", default="fr", help="Argos source language code (default: fr)")
    parser.add_argument("--target", default="en", help="Argos target language code (default: en)")
    parser.add_argument(
        "--segment",
        choices=("sentence", "line", "paragraph"),
        default="sentence",
        help="Alignment unit. Sentence is best for study; line is literal source lines.",
    )
    parser.add_argument("--output", type=Path, help="Output .parallel.json (default: beside input)")
    parser.add_argument("--source-title", default="", help="Display title for original")
    parser.add_argument("--target-title", default="", help="Display title for translation")
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0, help="Translate only the first N segments (0 = all)")
    parser.add_argument("--overwrite", action="store_true", help="Discard an incompatible existing output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path: Path = args.input.resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    if input_path.suffix.lower() != ".txt":
        raise SystemExit("Input must be a .txt file")

    raw = input_path.read_text(encoding="utf-8", errors="replace")
    digest = source_hash(raw)
    source_segments = segment_text(raw, args.segment)
    if args.limit > 0:
        source_segments = source_segments[: args.limit]
    if not source_segments:
        raise SystemExit("No translatable segments found")

    output: Path = (
        args.output.resolve()
        if args.output
        else input_path.with_name(f"{input_path.stem}.parallel.json")
    )

    completed: list[dict] = []
    if output.exists() and not args.overwrite:
        existing = json.loads(output.read_text(encoding="utf-8"))
        compatible = (
            existing.get("sourceSha256") == digest
            and existing.get("segmentation") == args.segment
            and str(existing.get("sourceLanguage", "")).lower().startswith(args.source.lower())
            and str(existing.get("targetLanguage", "")).lower().startswith(args.target.lower())
        )
        if not compatible:
            raise SystemExit(
                f"Existing output is not resumable: {output}\n"
                "Use --overwrite to replace it."
            )
        old_segments = existing.get("segments", [])
        for index, old in enumerate(old_segments):
            if index >= len(source_segments) or old.get("source") != source_segments[index]:
                break
            if old.get("target"):
                completed.append(old)
            else:
                break
        print(f"[parallel] resuming after {len(completed)} segments")

    translate = argos_translator(args.source, args.target)
    source_title = args.source_title or input_path.stem
    target_title = args.target_title or f"{source_title} ({args.target})"

    print(
        f"[parallel] {input_path.name}: {len(source_segments)} segments, "
        f"{args.source}->{args.target}, mode={args.segment}"
    )

    for index in range(len(completed), len(source_segments)):
        source = source_segments[index]
        target = translate(source).strip()
        completed.append({"id": index + 1, "source": source, "target": target})

        done = index + 1
        if done % max(1, args.checkpoint_every) == 0 or done == len(source_segments):
            write_checkpoint(
                output,
                source_lang=args.source,
                target_lang=args.target,
                source_title=source_title,
                target_title=target_title,
                digest=digest,
                mode=args.segment,
                segments=completed,
            )
            print(f"[parallel] {done}/{len(source_segments)} -> {output}")

    print(f"[parallel] done: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
