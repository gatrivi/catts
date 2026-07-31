"""Persistent XTTS worker — loads model once, accepts JSON lines on stdin."""
import json
import sys
from pathlib import Path

from _local_cache import configure_project_cache

VALID_LANGS = frozenset(
    "en es fr de it pt pl tr ru nl cs ar zh ja hu ko".split()
)


def main() -> int:
    configure_project_cache()
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
            text = (req.get("text") or "").strip()[:4000]
            ref = req.get("ref")
            refs = req.get("refs") or ([ref] if ref else [])
            out = req.get("out")
            lang = (req.get("lang") or "en")[:2].lower()
            speed = float(req.get("speed") or 1.15)
            if lang not in VALID_LANGS:
                lang = "en"
            if not text or not refs or not out:
                raise ValueError("text, ref/refs, out required")
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Multi-clip refs + slightly faster speech reduce "drugged" Iberian drift.
            tts.tts_to_file(
                text=text,
                speaker_wav=refs if len(refs) > 1 else refs[0],
                language=lang,
                file_path=str(out_path),
                split_sentences=True,
                speed=speed,
                temperature=0.75,
                repetition_penalty=5.0,
                top_p=0.85,
                top_k=50,
            )
            print(json.dumps({"ok": True, "out": str(out_path)}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
