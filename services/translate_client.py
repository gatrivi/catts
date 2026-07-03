"""Offline EN↔ES translation via Argos Translate."""

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_ready = False
_PAIRS = {("en", "es"), ("es", "en")}


def available() -> bool:
    try:
        import argostranslate.package  # noqa: F401
        installed = argostranslate.package.get_installed_packages()
        pairs = {(p.from_code, p.to_code) for p in installed}
        return ("en", "es") in pairs and ("es", "en") in pairs
    except Exception:
        return False


def _ensure_packages() -> None:
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        import argostranslate.package
        import argostranslate.translate

        argostranslate.package.update_package_index()
        installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
        for from_code, to_code in _PAIRS:
            if (from_code, to_code) in installed:
                continue
            available_pkgs = argostranslate.package.get_available_packages()
            pkg = next((p for p in available_pkgs if p.from_code == from_code and p.to_code == to_code), None)
            if not pkg:
                raise RuntimeError(f"Argos package {from_code}→{to_code} not found — run setup_stt.ps1")
            download = pkg.download()
            argostranslate.package.install_from_path(download)
            logger.info("Installed Argos %s→%s", from_code, to_code)
        _ready = True


def translate(text: str, from_lang: str, to_lang: str) -> str:
    if not available():
        raise RuntimeError("Translation not installed — run scripts/setup_stt.ps1")
    from_lang = from_lang[:2].lower()
    to_lang = to_lang[:2].lower()
    if from_lang == to_lang:
        return text
    if (from_lang, to_lang) not in _PAIRS:
        raise ValueError("Only English ↔ Spanish supported")
    _ensure_packages()
    import argostranslate.translate
    return argostranslate.translate.translate(text, from_lang, to_lang)
