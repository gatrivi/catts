"""Offline translate EN↔ES via Argos (run in .venv)."""
import argparse
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def configure_argos_env() -> None:
    argos_home = ROOT / "data" / "argos_runtime"
    config_home = argos_home / "config"
    data_home = argos_home / "data"
    cache_home = argos_home / "cache"
    for path in (config_home, data_home, cache_home):
        path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CONFIG_HOME", str(config_home))
    os.environ.setdefault("XDG_DATA_HOME", str(data_home))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_home))
    os.environ.setdefault("ARGOS_CHUNK_TYPE", "ARGOSTRANSLATE")
    os.environ.setdefault("ARGOS_STANZA_AVAILABLE", "false")


def main() -> int:
    configure_argos_env()
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--from", dest="from_lang", required=True)
    p.add_argument("--to", dest="to_lang", required=True)
    args = p.parse_args()
    try:
        import argostranslate.package
        import argostranslate.sbd
        import argostranslate.translate

        installed = {(x.from_code, x.to_code) for x in argostranslate.package.get_installed_packages()}
        for fc, tc in [("en", "es"), ("es", "en")]:
            if (fc, tc) not in installed:
                argostranslate.package.update_package_index()
                pkgs = argostranslate.package.get_available_packages()
                pkg = next(p for p in pkgs if p.from_code == fc and p.to_code == tc)
                argostranslate.package.install_from_path(pkg.download())

        def split_sentences_offline(self, text: str) -> list[str]:
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
            return sentences or [text]

        argostranslate.sbd.StanzaSentencizer.split_sentences = split_sentences_offline
        out = argostranslate.translate.translate(args.text, args.from_lang[:2], args.to_lang[:2])
        print(json.dumps({"ok": True, "text": out}))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
