"""Open job output folder in the system file manager."""

import subprocess
import sys
from pathlib import Path


def reveal_in_folder(path: Path) -> None:
    path = path.resolve()
    target = path if path.is_dir() else path.parent
    if sys.platform == "win32":
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            subprocess.run(["explorer", str(target)], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)] if path.is_file() else ["open", str(target)], check=False)
    else:
        subprocess.run(["xdg-open", str(target)], check=False)
