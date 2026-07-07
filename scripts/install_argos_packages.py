"""Download Argos EN↔ES packages (run once after pip install argostranslate)."""
import os
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


def repair_permissions() -> None:
    argos_home = ROOT / "data" / "argos_runtime"
    if os.name != "nt" or not argos_home.exists():
        return
    import subprocess

    subprocess.run(
        ["icacls", str(argos_home), "/grant", f"{os.getlogin()}:F", "/T", "/C"],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    configure_argos_env()
    import argostranslate.package

    argostranslate.package.update_package_index()
    installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    for from_code, to_code in [("en", "es"), ("es", "en")]:
        if (from_code, to_code) in installed:
            print(f"already installed {from_code}->{to_code}")
            continue
        pkgs = argostranslate.package.get_available_packages()
        pkg = next((p for p in pkgs if p.from_code == from_code and p.to_code == to_code), None)
        if not pkg:
            print(f"package not found {from_code}->{to_code}", file=sys.stderr)
            return 1
        path = pkg.download()
        argostranslate.package.install_from_path(path)
        print(f"installed {from_code}->{to_code}")
    repair_permissions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
