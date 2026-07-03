"""Persistent XTTS worker — loads model once, accepts JSON lines on stdin."""
import json
import sys
from pathlib import Path

VALID_LANGS = frozenset(
    "en es fr de it pt pl tr ru nl cs ar zh ja hu ko".split()
)


def main() -> int:
    from TTS.api import TTS

    print("loading xtts model…", file=sys.stderr, flush=True)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    print("ready", file=sys.stderr, flush=True)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
            if req.get("cmd") == "ping":
                print(json.dumps({"ok": True}), flush=True)
                continue
            text = (req.get("text") or "").strip()[:480]
            ref = req.get("ref")
            out = req.get("out")
            lang = (req.get("lang") or "en")[:2].lower()
            if lang not in VALID_LANGS:
                lang = "en"
            if not text or not ref or not out:
                raise ValueError("text, ref, out required")
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tts.tts_to_file(text=text, speaker_wav=str(ref), language=lang, file_path=str(out_path))
            print(json.dumps({"ok": True, "out": str(out_path)}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
