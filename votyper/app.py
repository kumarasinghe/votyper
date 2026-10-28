"""The controller: ties hotkey, speech, typing, tray and settings together."""

import os
import signal
import threading

from . import __version__, config
from .blinker import Blinker
from .folders import open_folder
from .hotkey import Hotkey
from .hotkeys import HotkeyMatcher
from .idle import IdleTimer
from .keyboard import Keyboard, KeyListener
from .live_typer import LiveTyper
from .logs import log, setup as setup_logging
from .meeting import Meeting
from .sounds import play_start, play_stop
from .speech import Dictation
from .tray import Tray
from .ui import UI


DEFAULT_HOTKEY = "ctrl+space"
IDLE_UNLOAD_SECONDS = 20 * 60       # free the speech model after this long without use


class App:
    def __init__(self, hotkey: Hotkey):
        self.hotkey = hotkey
        self.state = "loading"              # loading -> idle <-> listening / meeting; idle <-> sleeping
        self._lock = threading.Lock()
        self.ui = UI()
        self.keyboard, self.listener, self.tray = Keyboard(), KeyListener(), Tray()
        self.matcher = HotkeyMatcher()
        self.typer = LiveTyper(self.keyboard)
        self.dictation = Dictation(self._heard)
        self.meeting = Meeting()
        self.blinker = Blinker(self._blink)     # reminds you that it is listening
        self.idle = IdleTimer(IDLE_UNLOAD_SECONDS, self._unload_model)

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
        keys = str(self.hotkey).upper()
        if self.state == "sleeping":
            return f"sleeping to save memory - press {keys} to wake up and start"
        if self.state == "meeting":
            return "meeting mode - transcribing and saving (hotkey is off)"
        return f"{self.state} - press {keys} to start/stop"

    def _set_state(self, state: str) -> None:
        self.state = state
        self.tray.update(state, self._tooltip())
        self.ui.post(lambda: self.ui.show_meeting_mode(state == "meeting"))

    def _blink(self, bright: bool) -> None:
        if self.state in ("listening", "meeting"):      # the same blink for both
            self.tray.update("listening" if bright else "listening_dim", self._tooltip())

    def _load_model(self) -> None:
        log.info("loading speech model...")
        self.dictation.load()
        self._set_state("idle")
        self.idle.restart()
        log.info("ready. Press %s to start/stop. Click the tray icon for settings.", self.hotkey)

    def _heard(self, line_id: int, text: str, final: bool) -> None:
        log.debug("heard %r", text)
        if self.state == "meeting":         # a meeting never types into other apps
            finished = self.meeting.heard(text, final)
            live = self.meeting.tail
            self.ui.post(lambda: self.ui.show_transcript_line(finished, live))
        else:
            self.typer.update(line_id, text)

    def toggle(self) -> None:
        """The hotkey: start or stop typing. It does nothing during a meeting."""
        with self._lock:
            if self.state == "listening":
                self._stop_listening()
            elif self.state == "idle":      # ignored while the model is loading
                self._start_listening()
            elif self.state == "sleeping":
                self._wake_and_start(self._start_listening)

    def toggle_meeting(self) -> None:
        """The Meeting mode button: start or stop the meeting."""
        with self._lock:
            if self.state == "meeting":
                self._stop_meeting()
            elif self.state == "listening":     # typing stops first
                self._stop_listening()
                self._start_meeting()
            elif self.state == "idle":
                self._start_meeting()
            elif self.state == "sleeping":
                self._wake_and_start(self._start_meeting)

    def _wake_and_start(self, start) -> None:
        """Bring the model back, then run start, all from one key press."""
        self._set_state("loading")
        log.info("waking up: loading the speech model")
        try:
            self.dictation.load()
        except Exception:
            log.exception("could not load the speech model")
            self._set_state("sleeping")
            return
        self._set_state("idle")
        start()

    def _unload_model(self) -> None:
        """Runs after IDLE_UNLOAD_SECONDS of quiet: free the model's memory."""
        with self._lock:
            if self.state != "idle":        # something started in the meantime
                return
            self.dictation.unload()
            self._set_state("sleeping")
            log.info("unloaded the speech model after %d minutes idle", IDLE_UNLOAD_SECONDS // 60)

    def _start_listening(self) -> None:
        self.idle.cancel()
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
        self.idle.restart()                 # the quiet period starts now

    def _start_meeting(self) -> None:
        self.idle.cancel()
        path = self.meeting.start()
        self.ui.post(lambda: self.ui.start_transcript(path))
        play_start()
        self._set_state("meeting")          # from now on, speech goes to the transcript
        self.dictation.start()
        self.blinker.start()

    def _stop_meeting(self) -> None:
        self.blinker.stop()
        self.dictation.stop()               # flushes the last words into the transcript
        self.meeting.stop()
        play_stop()
        self._set_state("idle")
        self.idle.restart()

    # -- settings -------------------------------------------------------------
    def show_settings(self) -> None:
        self.ui.show_settings(self.hotkey, self._record_hotkey, self.matcher.cancel_capture,
                              self._toggle_meeting_in_background,
                              lambda: open_folder(self.meeting.folder), self.ui.stop,
                              self.meeting.path, list(self.meeting.lines), self.meeting.tail)

    def _toggle_meeting_in_background(self) -> None:
        """Loading the model can take seconds; the window must not freeze meanwhile."""
        threading.Thread(target=self.toggle_meeting, daemon=True).start()

    def _record_hotkey(self, done) -> None:
        def got(hotkey: Hotkey) -> None:
            self.hotkey = hotkey
            self._bind_hotkey()
            config.save(hotkey=str(hotkey))
            self._set_state(self.state)     # refresh the tooltip
            done(hotkey)
        self.matcher.capture(got)

    def _shutdown(self) -> None:
        self.idle.cancel()
        self.blinker.stop()
        self.listener.close()
        self.tray.close()
        self.dictation.close()              # also releases the mic if listening
        self.meeting.stop()                 # saves a sentence cut off by quitting
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
