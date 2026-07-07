"""Run XTTS voice clone in isolated venv (.venv). Called as subprocess from CATTS API."""
import argparse
import sys
from pathlib import Path

from _local_cache import configure_project_cache


def main() -> int:
    configure_project_cache()
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--ref", required=True, help="Reference speaker wav")
    p.add_argument("--out", required=True)
    p.add_argument("--lang", default="en")
    args = p.parse_args()

    ref = Path(args.ref)
    out = Path(args.out)
    if not ref.is_file():
        print(f"reference missing: {ref}", file=sys.stderr)
        return 1

    text = args.text.strip()
    if not text:
        print("empty text", file=sys.stderr)
        return 1
    # XTTS is happiest with shorter utterances; job_runner already chunks.
    text = text[:480]

    from TTS.api import TTS

    lang = (args.lang or "en")[:2].lower()
    if lang not in ("en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu", "ko"):
        lang = "en"

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    out.parent.mkdir(parents=True, exist_ok=True)
    tts.tts_to_file(text=text, speaker_wav=str(ref), language=lang, file_path=str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
