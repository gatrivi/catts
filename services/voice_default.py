"""Default voice for dev / single-user setups."""

from config import DEFAULT_VOICE_ID
from db import get_voice, list_voices


def resolve_default_voice_id() -> str | None:
    if DEFAULT_VOICE_ID:
        if get_voice(DEFAULT_VOICE_ID):
            return DEFAULT_VOICE_ID
    for voice in list_voices():
        if voice.get("status") == "ready":
            return voice["id"]
    return None
