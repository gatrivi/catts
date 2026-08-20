# Cloud status: Mastering the Core Teachings of the Buddha

Date: 2026-08-20

## Current truth

- Target is **Spanish TTS**, not English.
- The repository currently contains only English source chapters for this book.
- No Spanish translation or Spanish audio is ready.
- The previous English/garbled audio attempt is rejected as unusable.

## Text preparation run

- Source: `data/books/vv_chapters/core_teachings_take2/`
- Chapters: 35; originals preserved.
- Prepared diagnostic output: `data/books/vv_chapters/core_teachings_take2_prepared/`
- Report: `data/books/vv_chapters/core_teachings_take2_prepared/report.json`
- Cleaner removed hard line-wrap pauses; no mojibake markers were detected.
- Report still flags page-like tokens throughout the source and an uppercase run (`THIS IS IT`) in chapter 29.
- Large chapters needing review/splitting before synthesis: 23 (20,515 words), 29 (26,819), 35 (5,935).

## Decision gate

Do **not** start audiobook TTS. First produce/review a Spanish translation, then run Spanish-specific cleanup and a chapter-one audio smoke test. Preserve English originals and use a Spanish engine/voice; do not use Edge.

