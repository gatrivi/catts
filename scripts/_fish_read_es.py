"""One-shot Fish Speech ES readout with Gaston reference (msgpack API)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import ormsgpack

TEXT = """Mientras más débil sea nuestra realidad e Identidad, más fácil es dejarnos afectar por lo que los demás dicen, piensan, o nos hacen creer que piensan. Lo cual nos distrae de nuestras metas, dirigiendo nuestra atención hacia futuros posibles poco gratos.

Ser este tipo de persona emocionalmente volátil, es una estrategia inefectiva de vida para elegir."""

REF = Path(r"E:\zengatrivi-drive-e\catts\data\voices\gaston-esp\fish_ref_15s.wav")
OUT = Path(r"E:\zengatrivi-drive-e\catts\data\fish_gaston_es.wav")
URL = "http://127.0.0.1:8080/v1/tts"


def main() -> int:
    # Prefer fish venv packages if present
    if not REF.is_file():
        print("missing ref", REF, file=sys.stderr)
        return 1

    from fish_speech.utils.schema import ServeReferenceAudio, ServeTTSRequest

    req = ServeTTSRequest(
        text=TEXT,
        references=[ServeReferenceAudio(audio=REF.read_bytes(), text="")],
        format="wav",
        chunk_length=200,
        max_new_tokens=512,
    )
    body = ormsgpack.packb(req, option=ormsgpack.OPT_SERIALIZE_PYDANTIC)
    print("POST", URL, "ref_kb", REF.stat().st_size // 1024, "payload_kb", len(body) // 1024)
    t0 = time.perf_counter()
    with httpx.Client(timeout=900.0) as client:
        r = client.post(
            URL,
            content=body,
            headers={"content-type": "application/msgpack"},
        )
        print("status", r.status_code, "ctype", r.headers.get("content-type"), "bytes", len(r.content))
        if r.status_code >= 400:
            print(r.content[:800], file=sys.stderr)
            return 1
        OUT.write_bytes(r.content)
    print("wrote", OUT, "sec", round(time.perf_counter() - t0, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
