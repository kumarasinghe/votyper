"""Microphone -> text, using Moonshine. Reports live text per utterance."""

import gc
from typing import Callable

from .logs import log

OnText = Callable[[int, str, bool], None]   # (line_id, text so far, line is finished)

LANGUAGE = "en"


class Dictation:
    """Load the model once; open the microphone only while dictating."""

    def __init__(self, on_text: OnText):
        self._on_text = on_text
        self._transcriber = None
        self._mic = None

    def load(self) -> None:
        """Open the model (slow the first time)."""
        from moonshine_voice.download import get_model_for_language
        from moonshine_voice.transcriber import Transcriber
        path, arch = get_model_for_language(LANGUAGE, None)
        self._transcriber = Transcriber(str(path), arch)

    def start(self) -> None:
        """Open the microphone and start transcribing."""
        from moonshine_voice.mic_transcriber import MicTranscriber
        from moonshine_voice.transcriber import LineCompleted, LineTextChanged
        mic = MicTranscriber().use_transcriber(self._transcriber).update_interval(0.25)
        # Both events carry the full text of the line; only LineCompleted is final.
        mic.add_listener(
            lambda ev: self._on_text(ev.line.line_id, ev.line.text, isinstance(ev, LineCompleted))
            if isinstance(ev, (LineTextChanged, LineCompleted)) else None)
        mic.on_error(lambda e: log.error("speech error: %s", e))
        self._mic = mic.load().start()

    def stop(self) -> None:
        """Flush the last words, then release the microphone."""
        if self._mic:
            self._mic.stop()    # final text arrives here
            self._mic.close()   # frees the audio device (mic indicator goes off)
            self._mic = None

    def unload(self) -> None:
        """Free the model's memory (about 475 MB); load() brings it back."""
        self.stop()
        if self._transcriber:
            self._transcriber.close()
            self._transcriber = None
            gc.collect()

    def close(self) -> None:
        self.unload()
