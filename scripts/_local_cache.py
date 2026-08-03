"""Project-local cache helpers for subprocess model scripts."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_project_cache() -> None:
    """Keep model downloads/caches on the repo drive (E:), not C:."""
    cache_home = ROOT / "data" / "model_cache"
    config_home = ROOT / "data" / "model_config"
    data_home = ROOT / "data" / "model_data"
    local_appdata = ROOT / "data" / "local_appdata"
    hf_home = ROOT / "data" / "huggingface"
    torch_home = ROOT / "data" / "torch"
    for path in (cache_home, config_home, data_home, local_appdata, hf_home, torch_home):
        path.mkdir(parents=True, exist_ok=True)

    # ponytail: force E: — huggingface_hub ignores XDG_CACHE_HOME on Windows.
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HF_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(hf_home / "transformers")
    os.environ["TORCH_HOME"] = str(torch_home)
    # Supertonic — pin off C: (~/.cache/supertonic3 by default)
    st_cache = ROOT / "data" / "supertonic3"
    st_cache.mkdir(parents=True, exist_ok=True)
    os.environ["SUPERTONIC_CACHE_DIR"] = str(st_cache)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_home))
    os.environ.setdefault("XDG_CONFIG_HOME", str(config_home))
    os.environ.setdefault("XDG_DATA_HOME", str(data_home))
    os.environ.setdefault("LOCALAPPDATA", str(local_appdata))
    os.environ.setdefault("TTS_HOME", str(local_appdata / "tts"))
    if os.getenv("CATTS_ACCEPT_COQUI_CPML", "").lower() in {"1", "true", "yes"}:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
