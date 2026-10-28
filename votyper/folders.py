"""Open a folder in the desktop's file manager (Linux only)."""

import os
import subprocess

from .logs import log


def open_folder(path: str) -> None:
    """Create the folder if needed, then show it. A missing file manager only logs."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log.warning("cannot open the folder %s (%s)", path, e)
