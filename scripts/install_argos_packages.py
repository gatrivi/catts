"""Download Argos EN↔ES packages (run once after pip install argostranslate)."""
import sys


def main() -> int:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
