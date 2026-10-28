"""Tk user interface: one small settings window. Tk must run on the main thread."""

import base64
import queue

from . import __version__
from .icon import ICON_FILE, logo_png
from .logs import log
from .meeting import MEETINGS_FOLDER

CREDIT = "Speech recognition by Moonshine · moonshine.ai"
PREFERRED_FONTS = ("Inter", "Noto Sans", "Ubuntu", "Cantarell", "Open Sans", "Roboto",
                   "DejaVu Sans")      # the first one installed is used
FONT_SIZE = 10
BACKGROUND, BORDER, MUTED = "#f6f5f4", "#cdc7c2", "#77767b"
TOOLTIP_DELAY_MS = 400
PUMP_WINDOW_MS = 100                # how often calls from other threads are run: window open
PUMP_IDLE_MS = 250                  # ... and no window
LOGO_SIZE = 28                       # pixels, next to the app name


class Tooltip:
    """A small note that appears when the pointer rests on a widget."""

    def __init__(self, widget, text):
        self._widget, self._text = widget, text     # text: a function, so it is always current
        self._after = self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event) -> None:
        self._hide()
        self._after = self._widget.after(TOOLTIP_DELAY_MS, self._show)

    def _show(self) -> None:
        import tkinter as tk
        tip = self._tip = tk.Toplevel(self._widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=self._text(), background="#ffffe0", relief="solid",
                 borderwidth=1, padx=6, pady=2).pack()
        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        if self._after:
            self._widget.after_cancel(self._after)
            self._after = None
        if self._tip:
            self._tip.destroy()
            self._tip = None


class UI:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk        
        self._tk, self._ttk = tk, ttk
        self._root = tk.Tk()
        self._root.withdraw()               # no main window, only the dialog
        self._fonts = self._choose_fonts()
        self._apply_style()
        self._calls = queue.SimpleQueue()
        self._dialog = None
        self._text = self._meeting_button = self._status = None   # the window's widgets
        self._meeting_on = False
        self._meeting_path = ""             # the last transcript file, shown under the text
        self._root.after(PUMP_IDLE_MS, self._pump)

    def _apply_style(self) -> None:
        """Flat, light, GNOME-like look. Tk cannot use GTK themes, so we style its own 'clam'."""
        style = self._ttk.Style(self._root)
        style.theme_use("clam")
        style.configure(".", background=BACKGROUND, foreground="#2e3436")
        style.configure("TButton", padding=(12, 6), background="#ffffff", bordercolor=BORDER,
                        lightcolor="#ffffff", darkcolor="#ffffff", focuscolor=BACKGROUND)
        style.map("TButton", background=[("pressed", "#dcdad6"), ("active", "#ecebea")])
        style.configure("Danger.TButton", background="#c01c28", foreground="#ffffff",
                        bordercolor="#a51d2d", lightcolor="#c01c28", darkcolor="#c01c28")
        style.map("Danger.TButton", background=[("pressed", "#a51d2d"), ("active", "#d03340")])
        style.configure("TScrollbar", background="#ffffff", troughcolor=BACKGROUND,
                        bordercolor=BORDER, arrowcolor="#5e5c64")

    def _choose_fonts(self) -> dict:
        """Use a clean sans font when the system has one; Tk's own default looks dated."""
        from tkinter import font
        installed = set(font.families(self._root))
        family = next((name for name in PREFERRED_FONTS if name in installed), None)
        base = font.nametofont("TkDefaultFont")
        if family:
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
                font.nametofont(name).configure(family=family, size=FONT_SIZE)
        family = family or base.actual("family")
        return {"title": (family, FONT_SIZE + 5, "bold"), "small": (family, FONT_SIZE - 1),
                "text": (family, FONT_SIZE + 1)}

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
        # Polling also lets Ctrl+C reach Python. Poll slowly while no window is open:
        # the app idles in the tray most of the time.
        delay = PUMP_WINDOW_MS if self._window_open() else PUMP_IDLE_MS
        self._root.after(delay, self._pump)

    # -- settings dialog ------------------------------------------------------
    def show_settings(self, hotkey, record, cancel_record, on_meeting, on_open_folder, on_quit,
                      meeting_path="", lines=(), live="") -> None:
        """Window with a row of buttons (hotkey, Meeting mode, Quit) above the live transcript.

        record(done): start listening for a key combination; calls done(hotkey)
        from any thread. cancel_record(): stop listening. on_meeting(): start or
        stop the meeting. on_open_folder(): show the saved transcripts.
        meeting_path, lines and live fill the transcript when the window is opened in the middle of a meeting (or after one).
        """
        if self._window_open():
            self._dialog.lift()
            return
        tk, ttk = self._tk, self._ttk
        win = self._dialog = tk.Toplevel(self._root)
        win.title("votyper")
        win.minsize(420, 380)
        win.configure(background=BACKGROUND)
        win.attributes("-topmost", True)
        self._set_icon(win)
        current_hotkey = tk.StringVar(value=str(hotkey).upper())
        recording = tk.BooleanVar(value=False)
        self._meeting_path = meeting_path or self._meeting_path

        def finish(new_hotkey=None):
            recording.set(False)
            if new_hotkey:
                current_hotkey.set(str(new_hotkey).upper())
            change.config(text="Change hotkey…")

        def on_change():
            if recording.get():             # button doubles as Cancel
                cancel_record()
                finish()
                return
            recording.set(True)
            change.config(text="Press the new keys… (click to cancel)")
            record(lambda hk: self.post(lambda: finish(hk)))

        def on_close():
            cancel_record()
            self._text = self._meeting_button = self._status = None
            win.destroy()

        # The logo on the left, then the app name; the version on the right.
        header = ttk.Frame(win)
        header.pack(fill="x", padx=20, pady=(14, 0))
        win.logo = tk.PhotoImage(data=base64.b64encode(logo_png(LOGO_SIZE)))  # keep alive
        ttk.Label(header, image=win.logo).pack(side="left")
        ttk.Label(header, text="Votyper", font=self._fonts["title"]).pack(side="left", padx=(8, 0))
        ttk.Label(header, text=f"version {__version__}", font=self._fonts["small"],
                  foreground=MUTED).pack(side="right")

        buttons = ttk.Frame(win)             # all the buttons side by side, on top
        buttons.pack(padx=20, pady=8)
        change = ttk.Button(buttons, text="Change hotkey…", command=on_change)
        change.pack(side="left", padx=4)
        Tooltip(change, lambda: f"Current hotkey: {current_hotkey.get()}")
        self._meeting_button = ttk.Button(buttons, command=on_meeting)
        self._meeting_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Open transcriptions", command=on_open_folder).pack(side="left", padx=4)
        ttk.Button(buttons, text="Quit votyper", command=on_quit).pack(side="left", padx=4)

        # The transcript fills the rest of the window. It can be selected and copied,
        # but not typed into.
        area = ttk.Frame(win)
        area.pack(fill="both", expand=True, padx=20)
        scrollbar = ttk.Scrollbar(area)
        scrollbar.pack(side="right", fill="y")
        self._text = tk.Text(area, wrap="word", width=56, height=12, state="disabled",
                             font=self._fonts["text"], padx=8, pady=6, relief="flat",
                             highlightthickness=1, highlightbackground=BORDER,
                             yscrollcommand=scrollbar.set)
        self._text.pack(side="left", fill="both", expand=True)
        self._make_copyable(self._text)
        scrollbar.config(command=self._text.yview)
        self._status = ttk.Label(win, font=self._fonts["small"], foreground=MUTED,
                                wraplength=380, justify="left")
        self._status.pack(padx=20, pady=(4, 0), anchor="w")
        ttk.Label(win, text=CREDIT, font=self._fonts["small"], foreground=MUTED).pack(pady=(6, 12))

        self._fill_transcript(lines, live)
        self._refresh_meeting_widgets()
        win.protocol("WM_DELETE_WINDOW", on_close)
        win.focus_force()

    @staticmethod
    def _make_copyable(text) -> None:
        """Let the read-only text be selected and copied: Ctrl+C, Ctrl+A and a right-click menu.

        Copying is done by hand instead of relying on Tk's defaults, which need the
        text to have the keyboard focus (a read-only text does not always get it).
        With nothing selected, Copy takes the whole transcript.
        """
        import tkinter as tk

        def copy(_event=None):
            try:
                chosen = text.get("sel.first", "sel.last")
            except tk.TclError:                 # nothing is selected
                chosen = text.get("1.0", "end-1c")
            text.clipboard_clear()
            text.clipboard_append(chosen)
            return "break"

        def select_all(_event=None):
            text.tag_add("sel", "1.0", "end-1c")
            return "break"

        def pressed(_event):
            text.focus_set()

        menu = tk.Menu(text, tearoff=False)
        menu.add_command(label="Copy", command=copy)
        menu.add_command(label="Select all", command=select_all)

        def right_click(event):
            text.focus_set()
            menu.tk_popup(event.x_root, event.y_root)

        text.bind("<Button-1>", pressed, add="+")
        text.bind("<Button-3>", right_click)
        for key in ("<Control-c>", "<Control-C>", "<<Copy>>"):
            text.bind(key, copy)
        for key in ("<Control-a>", "<Control-A>", "<<SelectAll>>"):
            text.bind(key, select_all)

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
            button.config(text="Stop meeting", style="Danger.TButton")
            self._status.config(text=f"Meeting mode is on. The hotkey is off. Saving to {self._meeting_path}")
        else:
            button.config(text="Meeting mode", style="TButton")
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
