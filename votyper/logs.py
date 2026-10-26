"""Logging: messages go to the terminal and to a rotating log file.

The file matters when votyper starts at login with no terminal to show errors:
~/.local/state/votyper/votyper.log
"""

import logging
import logging.handlers
import os
import sys
import threading

log = logging.getLogger("votyper")

MAX_LOG_BYTES = 200_000     # rotate at this size so the file never grows unbounded
KEPT_BACKUPS = 2


def log_path() -> str:
    state = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(state, "votyper", "votyper.log")


def setup(debug: bool = False) -> None:
    """Send log messages to the terminal and the log file."""
    log.setLevel(logging.DEBUG if debug else logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("votyper: %(message)s"))
    log.addHandler(console)

    try:
        os.makedirs(os.path.dirname(log_path()), exist_ok=True)
        to_file = logging.handlers.RotatingFileHandler(
            log_path(), maxBytes=MAX_LOG_BYTES, backupCount=KEPT_BACKUPS)
        to_file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(to_file)
    except OSError as e:                    # a read-only home must not stop dictation
        log.warning("cannot write log file (%s)", e)

    _log_uncaught_errors()


def _log_uncaught_errors() -> None:
    """Record crashes, in any thread, instead of losing them."""
    def main_thread_crash(kind, error, trace):
        log.critical("crashed", exc_info=(kind, error, trace))

    def worker_thread_crash(args):
        log.critical("thread %s crashed", args.thread.name,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = main_thread_crash
    threading.excepthook = worker_thread_crash
