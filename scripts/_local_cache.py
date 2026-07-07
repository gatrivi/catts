"""Project-local cache helpers for subprocess model scripts."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def configure_project_cache() -> None:
    cache_home = ROOT / "data" / "model_cache"
    config_home = ROOT / "data" / "model_config"
    local_appdata = ROOT / "data" / "local_appdata"
    for path in (cache_home, config_home, local_appdata):
        path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_home))
    os.environ.setdefault("XDG_CONFIG_HOME", str(config_home))
    os.environ.setdefault("LOCALAPPDATA", str(local_appdata))
    os.environ.setdefault("TTS_HOME", str(local_appdata / "tts"))
    if os.getenv("CATTS_ACCEPT_COQUI_CPML", "").lower() in {"1", "true", "yes"}:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
