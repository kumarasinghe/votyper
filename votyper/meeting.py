"""Meeting mode: keeps a transcript of what is said and saves it to a text file."""

import os
import re
from datetime import datetime, timezone

from .logs import log

MEETINGS_FOLDER = "~/.votyper/meetings"
SENTENCE_END = re.compile(r"[.?!…][\"')\]]*$")      # a sentence ends with . ? ! (and maybe a quote)


class Meeting:
    """One meeting: finished sentences go to a file, each followed by a blank line.

    The speech model cuts its text wherever you pause, which can be in the middle of
    a sentence. So pieces are joined until one ends with . ? or !, and only then is
    the sentence saved. The unfinished part is held in memory (`tail`). The file is
    private to you (0600) because a transcript can hold sensitive talk.
    """

    def __init__(self, folder: str = MEETINGS_FOLDER):
        self.folder = os.path.expanduser(folder)
        self._file = None
        self.path = ""
        self.lines = []             # finished sentences
        self._pieces = []           # finished pieces of the sentence being spoken
        self.live = ""              # the piece still being spoken

    @property
    def tail(self) -> str:
        """Everything said since the last finished sentence."""
        return " ".join(self._pieces + ([self.live] if self.live else []))

    def start(self) -> str:
        """Create the transcript file, named after the UTC start time. Returns its path."""
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = self._create_file(stamp)
        self.lines, self._pieces, self.live = [], [], ""
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

        Returns a sentence when this piece completes one, to append to the screen.
        Otherwise returns None, and `tail` shows the unfinished sentence.
        """
        text = text.strip()
        if not final:
            self.live = text
            return None
        self.live = ""
        if text:
            self._pieces.append(text)
        sentence = self.tail
        if not SENTENCE_END.search(sentence):
            return None
        self._pieces = []
        self._save(sentence)
        return sentence

    def stop(self) -> None:
        """Save a sentence that was cut off mid-way, then close the file."""
        if not self._file:                  # no meeting is running
            return
        if self.tail:
            self._save(self.tail)
            self._pieces, self.live = [], ""
        self._file.close()
        self._file = None
        log.info("meeting stopped, %d lines saved to %s", len(self.lines), self.path)

    def _save(self, sentence: str) -> None:
        """Keep a finished sentence, and write it to disk at once so a crash loses little."""
        self.lines.append(sentence)
        if not self._file:
            return
        try:
            self._file.write(sentence + "\n\n")
            self._file.flush()
        except OSError as e:        # e.g. disk full: keep the meeting going on screen
            log.error("cannot save the transcript (%s)", e)
