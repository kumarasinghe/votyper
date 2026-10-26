"""Calls a function with True/False alternately, e.g. to blink the tray icon."""

import threading

BLINK_SECONDS = 0.6


class Blinker:
    def __init__(self, on_change, period: float = BLINK_SECONDS):
        self._on_change, self._period = on_change, period
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        """Begin with 'on', then alternate every period until stop()."""
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        on = True
        self._on_change(on)
        while not self._stop.wait(self._period):
            on = not on
            self._on_change(on)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)    # so no late change overwrites what comes next
            self._thread = None
