"""Run XTTS voice clone in isolated venv (.venv). Called as subprocess from CATTS API."""
import argparse
import sys
from pathlib import Path

from _local_cache import configure_project_cache


def main() -> int:
    configure_project_cache()
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--ref", required=True, help="Primary reference speaker wav")
    p.add_argument("--ref-extra", action="append", default=[], help="Extra ref clips")
    p.add_argument("--out", required=True)
    p.add_argument("--lang", default="en")
    p.add_argument("--speed", type=float, default=1.15)
    args = p.parse_args()

    refs = [Path(args.ref), *[Path(x) for x in args.ref_extra]]
    out = Path(args.out)
    for ref in refs:
        if not ref.is_file():
            print(f"reference missing: {ref}", file=sys.stderr)
            return 1

    text = args.text.strip()
    if not text:
        print("empty text", file=sys.stderr)
        return 1
    text = text[:4000]

    from TTS.api import TTS

    lang = (args.lang or "en")[:2].lower()
    if lang not in ("en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu", "ko"):
        lang = "en"

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    out.parent.mkdir(parents=True, exist_ok=True)
    speaker = [str(r) for r in refs]
    tts.tts_to_file(
        text=text,
        speaker_wav=speaker if len(speaker) > 1 else speaker[0],
        language=lang,
        file_path=str(out),
        split_sentences=True,
        speed=float(args.speed),
        temperature=0.75,
        repetition_penalty=5.0,
        top_p=0.85,
        top_k=50,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
