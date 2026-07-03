"""Offline translate EN↔ES via Argos (run in .venv)."""
import argparse
import json
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--from", dest="from_lang", required=True)
    p.add_argument("--to", dest="to_lang", required=True)
    args = p.parse_args()
    try:
        import argostranslate.package
        import argostranslate.translate

        argostranslate.package.update_package_index()
        installed = {(x.from_code, x.to_code) for x in argostranslate.package.get_installed_packages()}
        for fc, tc in [("en", "es"), ("es", "en")]:
            if (fc, tc) not in installed:
                pkgs = argostranslate.package.get_available_packages()
                pkg = next(p for p in pkgs if p.from_code == fc and p.to_code == tc)
                argostranslate.package.install_from_path(pkg.download())
        out = argostranslate.translate.translate(args.text, args.from_lang[:2], args.to_lang[:2])
        print(json.dumps({"ok": True, "text": out}))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
