"""Meeting mode: keeps a transcript of what is said and saves it to a text file."""

import os
from datetime import datetime, timezone

from .logs import log

MEETINGS_FOLDER = "~/.votyper/meetings"


class Meeting:
    """One meeting: finished sentences go to a file, one per line, as they are said.

    The speech model keeps revising the sentence being spoken, so that sentence is
    only held in memory (`live`) until the model completes it. The file is private
    to you (0600) because a transcript can hold sensitive talk.
    """

    def __init__(self, folder: str = MEETINGS_FOLDER):
        self.folder = os.path.expanduser(folder)
        self._file = None
        self.path = ""
        self.lines = []             # finished sentences
        self.live = ""              # the sentence still being spoken

    def start(self) -> str:
        """Create the transcript file, named after the UTC start time. Returns its path."""
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = self._create_file(stamp)
        self.lines, self.live = [], ""
        log.info("meeting started, saving to %s", self.path)
        return self.path

    def _create_file(self, stamp: str) -> str:
        """Open <stamp>.txt, or <stamp>-2.txt... if a meeting already began this second."""
        attempt = 1
        while True:
            suffix = "" if attempt == 1 else f"-{attempt}"
            path = os.path.join(self.folder, f"{stamp}{suffix}.txt")
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                attempt += 1
                continue
            self._file = os.fdopen(fd, "w", encoding="utf-8")
            return path

    def heard(self, text: str, final: bool) -> str | None:
        """Take the speech model's latest words.

        Returns the finished sentence to append to the screen when `final` (an
        empty string when there was nothing to keep), or None while the sentence
        is still changing.
        """
        text = text.strip()
        if not final:
            self.live = text
            return None
        self.live = ""
        if text:
            self.lines.append(text)
            self._write(text)
        return text

    def stop(self) -> None:
        """Save a sentence that was cut off mid-way, then close the file."""
        if not self._file:                  # no meeting is running
            return
        if self.live:
            self.lines.append(self.live)
            self._write(self.live)
            self.live = ""
        self._file.close()
        self._file = None
        log.info("meeting stopped, %d lines saved to %s", len(self.lines), self.path)

    def _write(self, line: str) -> None:
        """Write one line to disk at once, so a crash loses at most the live sentence."""
        if not self._file:
            return
        try:
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as e:        # e.g. disk full: keep the meeting going on screen
            log.error("cannot save the transcript (%s)", e)
