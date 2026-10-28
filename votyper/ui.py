"""Tk user interface: one small settings window. Tk must run on the main thread."""

import base64
import queue

from . import __version__
from .icon import ICON_FILE, logo_png
from .logs import log
from .meeting import MEETINGS_FOLDER

CREDIT = "Speech recognition by Moonshine · moonshine.ai"
LOGO_SIZE = 28                       # pixels, next to the app name


class UI:
    def __init__(self):
        import tkinter as tk
        self._tk = tk
        self._root = tk.Tk()
        self._root.withdraw()               # no main window, only the dialog
        self._calls = queue.SimpleQueue()
        self._dialog = None
        self._text = self._meeting_button = self._status = None   # the window's widgets
        self._meeting_on = False
        self._meeting_path = ""             # the last transcript file, shown under the text
        self._root.after(50, self._pump)

    # -- thread-safe entry points -------------------------------------------
    def post(self, fn) -> None:
        """Run fn on the UI thread (callable from any thread)."""
        self._calls.put(fn)

    def stop(self) -> None:
        self.post(self._root.quit)

    def run(self) -> None:
        self._root.mainloop()

    def _pump(self) -> None:
        while not self._calls.empty():
            try:
                self._calls.get()()
            except Exception as e:
                log.error("ui error: %s", e)
        self._root.after(50, self._pump)    # also lets Ctrl+C reach Python

    # -- settings dialog ------------------------------------------------------
    def show_settings(self, hotkey, record, cancel_record, on_meeting, on_quit,
                      meeting_path="", lines=(), live="") -> None:
        """Window with a row of buttons (hotkey, Meeting mode, Quit) above the live transcript.

        record(done): start listening for a key combination; calls done(hotkey)
        from any thread. cancel_record(): stop listening. on_meeting(): start or
        stop the meeting. meeting_path, lines and live fill the transcript when the
        window is opened in the middle of a meeting (or after one).
        """
        if self._window_open():
            self._dialog.lift()
            return
        tk = self._tk
        win = self._dialog = tk.Toplevel(self._root)
        win.title("votyper")
        win.minsize(420, 380)
        win.attributes("-topmost", True)
        self._set_icon(win)
        shown = tk.StringVar(value=str(hotkey).upper())
        recording = tk.BooleanVar(value=False)
        self._meeting_path = meeting_path or self._meeting_path

        def finish(new_hotkey=None):
            recording.set(False)
            if new_hotkey:
                shown.set(str(new_hotkey).upper())
            change.config(text="Change hotkey…")

        def on_change():
            if recording.get():             # button doubles as Cancel
                cancel_record()
                finish()
                return
            recording.set(True)
            shown.set("Press the new keys…")
            change.config(text="Cancel")
            record(lambda hk: self.post(lambda: finish(hk)))

        def on_close():
            cancel_record()
            self._text = self._meeting_button = self._status = None
            win.destroy()

        header = tk.Frame(win)              # the app name followed by the logo
        header.pack(padx=20, pady=(14, 0))
        tk.Label(header, text="Votyper", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        win.logo = tk.PhotoImage(data=base64.b64encode(logo_png(LOGO_SIZE)))  # keep alive
        tk.Label(header, image=win.logo).pack(side="left", padx=(8, 0))
        tk.Label(win, text=f"version {__version__}", font=("TkDefaultFont", 8),
                 fg="gray50").pack()
        hotkey_row = tk.Frame(win)
        hotkey_row.pack(pady=(10, 0))
        tk.Label(hotkey_row, text="Dictation hotkey").pack(side="left")
        tk.Label(hotkey_row, textvariable=shown, font=("TkDefaultFont", 12, "bold")).pack(
            side="left", padx=(8, 0))

        buttons = tk.Frame(win)             # all the buttons side by side, on top
        buttons.pack(padx=20, pady=8)
        change = tk.Button(buttons, text="Change hotkey…", command=on_change)
        change.pack(side="left", padx=4)
        self._meeting_button = tk.Button(buttons, command=on_meeting)
        self._meeting_button.pack(side="left", padx=4)
        tk.Button(buttons, text="Quit votyper", command=on_quit).pack(side="left", padx=4)

        # The transcript fills the rest of the window. It can be selected and copied,
        # but not typed into.
        area = tk.Frame(win)
        area.pack(fill="both", expand=True, padx=20)
        scrollbar = tk.Scrollbar(area)
        scrollbar.pack(side="right", fill="y")
        self._text = tk.Text(area, wrap="word", width=56, height=12, state="disabled",
                             yscrollcommand=scrollbar.set)
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)
        self._status = tk.Label(win, font=("TkDefaultFont", 8), fg="gray50",
                                wraplength=380, justify="left")
        self._status.pack(padx=20, pady=(4, 0), anchor="w")
        tk.Label(win, text=CREDIT, font=("TkDefaultFont", 8), fg="gray50").pack(pady=(6, 12))

        self._fill_transcript(lines, live)
        self._refresh_meeting_widgets()
        win.protocol("WM_DELETE_WINDOW", on_close)
        win.focus_force()

    # -- meeting transcript ---------------------------------------------------
    def _window_open(self) -> bool:
        return bool(self._dialog and self._dialog.winfo_exists())

    def show_meeting_mode(self, on: bool) -> None:
        """Tell the window whether a meeting is running (UI thread)."""
        self._meeting_on = on
        self._refresh_meeting_widgets()

    def start_transcript(self, path: str) -> None:
        """A new meeting began: clear the text and show where it is saved (UI thread)."""
        self._meeting_path = path
        self._fill_transcript([], "")
        self._refresh_meeting_widgets()

    def show_transcript_line(self, finished, live: str) -> None:
        """Append a finished sentence, or show the sentence still being spoken (UI thread)."""
        def edit(text):
            text.delete("live", "end-1c")           # drop the old guess of the live sentence
            if finished is None:
                text.insert("live", live)
                return
            if finished:
                text.insert("live", finished + "\n")
            text.mark_set("live", "end-1c")
        self._edit_transcript(edit)

    def _fill_transcript(self, lines, live: str) -> None:
        def edit(text):
            text.delete("1.0", "end")
            for line in lines:
                text.insert("end", line + "\n")
            text.mark_set("live", "end-1c")
            text.mark_gravity("live", "left")       # new text goes after the mark
            text.insert("live", live)
        self._edit_transcript(edit, follow=True)

    def _edit_transcript(self, edit, follow=None) -> None:
        """Run edit(text) on the read-only text; keep the end in view if the reader is there."""
        text = self._text
        if not text:
            return
        if follow is None:
            follow = text.yview()[1] >= 0.99
        text.config(state="normal")
        edit(text)
        text.config(state="disabled")
        if follow:
            text.see("end")

    def _refresh_meeting_widgets(self) -> None:
        if not self._window_open():
            return
        button = self._meeting_button
        if self._meeting_on:
            button.config(text="Stop meeting", relief="sunken")
            self._status.config(text=f"Meeting mode is on. The hotkey is off. Saving to {self._meeting_path}")
        else:
            button.config(text="Meeting mode", relief="raised")
            if self._meeting_path:
                self._status.config(text=f"Saved to {self._meeting_path}")
            else:
                self._status.config(
                    text=f"Meeting mode shows a live transcript here and saves it in {MEETINGS_FOLDER}")

    def _set_icon(self, window) -> None:
        """Give the window the app icon; a missing icon must never break the dialog."""
        try:
            window.icon = self._tk.PhotoImage(file=str(ICON_FILE))  # keep a reference alive
            window.iconphoto(True, window.icon)
        except self._tk.TclError as e:
            log.warning("cannot load window icon (%s)", e)
