"""Turns raw key events into hotkey presses. Shared by every OS.

The key listener only has to report "key X went down/up" using neutral names
("f9", "a", "ctrl"...). Matching, modifiers and recording live here.
"""

import threading

from .hotkey import MODIFIERS, Hotkey


def _run(callback, *args) -> None:
    """Callbacks run off the listener thread so it never blocks."""
    threading.Thread(target=callback, args=args, daemon=True).start()


class HotkeyMatcher:
    def __init__(self):
        self._held = set()
        self._binding = None        # (Hotkey, callback)
        self._capture = None        # callback(Hotkey) for "record next combo"

    def bind(self, hotkey: Hotkey, callback) -> None:
        self._binding = (hotkey, callback)

    def capture(self, callback) -> None:
        """Send the next key combination to callback(hotkey) instead of firing."""
        self._capture = callback

    def cancel_capture(self) -> None:
        self._capture = None

    def feed(self, key: str, down: bool) -> None:
        if not down:
            self._held.discard(key)
            return
        if key in self._held:       # auto-repeat
            return
        self._held.add(key)
        if key in MODIFIERS:
            return
        combo = Hotkey(key, frozenset(self._held & set(MODIFIERS)))
        capture, self._capture = self._capture, None
        if capture:
            _run(capture, combo)
        elif self._binding and combo == self._binding[0]:
            _run(self._binding[1])
