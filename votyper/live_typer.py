"""Turns a changing transcript into keystrokes, correcting as the text is revised."""

import threading
from os.path import commonprefix
from typing import Protocol


class Keyboard(Protocol):
    def type_text(self, text: str) -> None: ...
    def backspace(self, count: int) -> None: ...


class LiveTyper:
    """Keeps the focused text field equal to the transcript.

    The speech model revises its guess while you talk ("recognize" -> "wreck a
    nice"). We only erase the part that differs from what is already typed, so
    stable text is never retyped.
    """

    def __init__(self, keyboard: Keyboard):
        self._kb = keyboard
        self._lock = threading.Lock()   # speech and hotkey threads both call in
        self.reset()

    def update(self, line_id: int, text: str) -> None:
        """Show `text` as the current state of line `line_id`."""
        with self._lock:
            if line_id != self._line_id:                    # new utterance
                self._line_id, self._typed = line_id, ""
                self._prefix = " " if self._typed_any else ""
            text = text.strip()
            target = self._prefix + text if text else ""
            keep = len(commonprefix([self._typed, target]))
            if len(self._typed) > keep:
                self._kb.backspace(len(self._typed) - keep)
            if len(target) > keep:
                self._kb.type_text(target[keep:])
                self._typed_any = True
            self._typed = target

    def reset(self) -> None:
        """Forget the current session; the next dictation starts fresh."""
        self._line_id, self._typed, self._typed_any, self._prefix = None, "", False, ""
