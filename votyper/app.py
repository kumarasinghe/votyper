"""The controller: ties hotkey, speech, typing, tray and settings together."""

import os
import signal
import threading

from . import __version__, config
from .blinker import Blinker
from .hotkey import Hotkey
from .hotkeys import HotkeyMatcher
from .keyboard import Keyboard, KeyListener
from .live_typer import LiveTyper
from .logs import log, setup as setup_logging
from .sounds import play_start, play_stop
from .speech import Dictation
from .tray import Tray
from .ui import UI


DEFAULT_HOTKEY = "ctrl+space"


class App:
    def __init__(self, hotkey: Hotkey):
        self.hotkey = hotkey
        self.state = "loading"              # loading -> idle <-> listening
        self._lock = threading.Lock()
        self.ui = UI()
        self.keyboard, self.listener, self.tray = Keyboard(), KeyListener(), Tray()
        self.matcher = HotkeyMatcher()
        self.typer = LiveTyper(self.keyboard)
        self.dictation = Dictation(self._heard)
        self.blinker = Blinker(self._blink)     # reminds you that it is listening

    def run(self) -> None:
        self._bind_hotkey()
        self.listener.start(self.matcher.feed)
        self.tray.start(lambda: self.ui.post(self.show_settings))
        self._set_state("loading")
        threading.Thread(target=self._load_model, daemon=True).start()
        signal.signal(signal.SIGINT, lambda *_: self.ui.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.ui.stop())
        self.ui.run()
        self._shutdown()

    # -- state ----------------------------------------------------------------
    def _bind_hotkey(self) -> None:
        self.matcher.bind(self.hotkey, self.toggle)

    def _tooltip(self) -> str:
        return f"{self.state} - press {str(self.hotkey).upper()} to start/stop"

    def _set_state(self, state: str) -> None:
        self.state = state
        self.tray.update(state, self._tooltip())

    def _blink(self, bright: bool) -> None:
        if self.state == "listening":
            self.tray.update("listening" if bright else "listening_dim", self._tooltip())

    def _load_model(self) -> None:
        log.info("loading speech model...")
        self.dictation.load()
        self._set_state("idle")
        log.info("ready. Press %s to start/stop. Click the tray icon for settings.", self.hotkey)

    def _heard(self, line_id: int, text: str) -> None:
        log.debug("heard %r", text)
        self.typer.update(line_id, text)

    def toggle(self) -> None:
        with self._lock:
            if self.state == "listening":
                self._stop_listening()
            elif self.state == "idle":      # ignored while the model is still loading
                self._start_listening()

    def _start_listening(self) -> None:
        self.typer.reset()
        play_start()
        self.dictation.start()
        self._set_state("listening")
        self.blinker.start()

    def _stop_listening(self) -> None:
        self.blinker.stop()
        self.dictation.stop()               # flushes the last words
        self.typer.reset()
        play_stop()
        self._set_state("idle")

    # -- settings -------------------------------------------------------------
    def show_settings(self) -> None:
        self.ui.show_settings(self.hotkey, self._record_hotkey, self.matcher.cancel_capture,
                              self.ui.stop)

    def _record_hotkey(self, done) -> None:
        def got(hotkey: Hotkey) -> None:
            self.hotkey = hotkey
            self._bind_hotkey()
            config.save(hotkey=str(hotkey))
            self._set_state(self.state)     # refresh the tooltip
            done(hotkey)
        self.matcher.capture(got)

    def _shutdown(self) -> None:
        self.blinker.stop()
        self.listener.close()
        self.tray.close()
        self.dictation.close()              # also releases the mic if listening
        self.keyboard.close()


def main() -> int:
    # Set VOTYPER_DEBUG=1 to also log what the model hears (your speech, so off by default).
    setup_logging(debug=bool(os.environ.get("VOTYPER_DEBUG")))
    log.info("Votyper %s starting", __version__)
    try:
        App(Hotkey.parse(config.load().get("hotkey", DEFAULT_HOTKEY))).run()
    except Exception:                       # e.g. no /dev/uinput access: leave a trace
        log.exception("could not start")
        return 1
    return 0
