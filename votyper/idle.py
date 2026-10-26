"""A restartable one-shot timer: calls a function once after a quiet period."""

import threading


class IdleTimer:
    def __init__(self, seconds: float, callback):
        self._seconds, self._callback = seconds, callback
        self._timer = None
        self._lock = threading.Lock()

    def restart(self) -> None:
        """Start counting from zero again (cancelling any count in progress)."""
        with self._lock:
            self._cancel()
            self._timer = threading.Timer(self._seconds, self._callback)
            self._timer.daemon = True           # never keeps the app alive on exit
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            self._cancel()

    def _cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
