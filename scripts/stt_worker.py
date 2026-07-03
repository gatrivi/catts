"""Persistent faster-whisper worker (stdin JSON lines)."""
import json
import sys
import tempfile
from pathlib import Path

VALID_LANGS = frozenset({"en", "es", "auto"})


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "small"
    from faster_whisper import WhisperModel

    print(f"loading whisper {model_name}…", file=sys.stderr, flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
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
            audio_b64 = req.get("audio_b64")
            audio_path = req.get("audio_path")
            lang = (req.get("lang") or "auto").lower()
            if lang not in VALID_LANGS:
                lang = "auto"
            whisper_lang = None if lang == "auto" else lang

            tmp_path = None
            if audio_b64:
                import base64
                data = base64.b64decode(audio_b64)
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.write(data)
                tmp.close()
                tmp_path = Path(tmp.name)
                audio_path = str(tmp_path)
            if not audio_path or not Path(audio_path).is_file():
                raise ValueError("audio_path or audio_b64 required")

            segments, info = model.transcribe(
                audio_path,
                language=whisper_lang,
                vad_filter=True,
                beam_size=5,
            )
            text = "".join(seg.text for seg in segments).strip()
            detected = getattr(info, "language", None) or lang
            print(
                json.dumps({"ok": True, "text": text, "language": detected}),
                flush=True,
            )
            if tmp_path:
                tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
