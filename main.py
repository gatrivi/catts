#!/usr/bin/env python3
"""CLI entry — process OCR text into chapter files."""

import argparse
import json
import os

from text_processor import process_book


def main():
    parser = argparse.ArgumentParser(description="Process book text into chapters for TTS")
    parser.add_argument("input_file", nargs="?", default="ocr_output.txt")
    parser.add_argument("--json", action="store_true", help="Write chapters.json")
    parser.add_argument("--min-chunk", type=int, default=200)
    parser.add_argument("--max-chunk", type=int, default=400)
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: File '{args.input_file}' not found.")
        return 1

    with open(args.input_file, encoding="utf-8") as f:
        ocr_text = f.read()

    chapters = process_book(ocr_text, args.min_chunk, args.max_chunk)
    os.makedirs("chapters", exist_ok=True)

    for i, chapter in enumerate(chapters):
        chapter_text = f"{chapter['title']}\n\n{chapter['content']}"
        path = f"chapters/chapter_{i + 1:03d}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(chapter_text)
        print(f"Processed chapter {i + 1}: {chapter['title']} ({len(chapter.get('chunks', []))} TTS chunks)")

    if args.json:
        with open("chapters/chapters.json", "w", encoding="utf-8") as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)

    print(f"All {len(chapters)} chapters processed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
