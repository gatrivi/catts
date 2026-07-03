"""Fix legacy voice rows with hex or placeholder names."""

from db import list_voices, update_voice
from services.voice_labels import sync_voice_labeled_files


def fix_legacy_voice_names() -> int:
    fixed = 0
    for voice in list_voices(500):
        name = (voice.get("name") or "").strip()
        vid = voice["id"]
        if name and name != vid and name.lower() not in ("voice", "default"):
            continue
        lang = voice.get("lang") or "en"
        new_name = "Mi voz principal" if lang.startswith("es") else "My main voice"
        fields = {"name": new_name}
        msg = voice.get("message") or ""
        if "stub mode" in msg.lower():
            fields["message"] = "Ready — preview sample saved"
        update_voice(vid, **fields)
        sync_voice_labeled_files(vid)
        fixed += 1
    return fixed
