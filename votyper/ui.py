"""Tk user interface: one small settings window. Tk must run on the main thread."""

import base64
import queue

from . import __version__
from .icon import ICON_FILE, logo_png
from .logs import log

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
    def show_settings(self, hotkey, record, cancel_record, on_quit) -> None:
        """Window with the hotkey, a Change button and Quit.

        record(done): start listening for a key combination; calls done(hotkey)
        from any thread. cancel_record(): stop listening.
        """
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.lift()
            return
        tk = self._tk
        win = self._dialog = tk.Toplevel(self._root)
        win.title("votyper")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        self._set_icon(win)
        shown = tk.StringVar(value=str(hotkey).upper())
        recording = tk.BooleanVar(value=False)

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
            win.destroy()

        pad = {"padx": 20, "pady": 6}
        header = tk.Frame(win)              # the app name followed by the logo
        header.pack(padx=20, pady=(14, 0))
        tk.Label(header, text="Votyper", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        win.logo = tk.PhotoImage(data=base64.b64encode(logo_png(LOGO_SIZE)))  # keep alive
        tk.Label(header, image=win.logo).pack(side="left", padx=(8, 0))
        tk.Label(win, text=f"version {__version__}", font=("TkDefaultFont", 8),
                 fg="gray50").pack()
        tk.Label(win, text="Dictation hotkey").pack(padx=20, pady=(14, 0))
        tk.Label(win, textvariable=shown, font=("TkDefaultFont", 16, "bold")).pack(**pad)
        change = tk.Button(win, text="Change hotkey…", command=on_change)
        change.pack(**pad)
        tk.Button(win, text="Quit votyper", command=on_quit).pack(padx=20, pady=(6, 14))
        tk.Label(win, text=CREDIT, font=("TkDefaultFont", 8), fg="gray50").pack(pady=(0, 12))
        win.protocol("WM_DELETE_WINDOW", on_close)
        win.focus_force()

    def _set_icon(self, window) -> None:
        """Give the window the app icon; a missing icon must never break the dialog."""
        try:
            window.icon = self._tk.PhotoImage(file=str(ICON_FILE))  # keep a reference alive
            window.iconphoto(True, window.icon)
        except self._tk.TclError as e:
            log.warning("cannot load window icon (%s)", e)
