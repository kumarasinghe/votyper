"""Open a folder in the system's file manager, on any operating system."""

import os
import subprocess
import sys

from .logs import log


def open_folder(path: str) -> None:
    """Create the folder if needed, then show it. A missing file manager only logs."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            command = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([command, path], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log.warning("cannot open the folder %s (%s)", path, e)
