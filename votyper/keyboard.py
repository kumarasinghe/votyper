"""Typing and key listening through /dev/uinput and /dev/input (X11 and Wayland).

Needs read access to /dev/input/event* and write access to /dev/uinput
(usually: be in the `input` group).

Limits: typed keys are *keycodes*, so characters follow a US layout; keys are
observed, not grabbed, so the focused app also sees the hotkey.
"""

import fcntl
import os
import selectors
import struct
import threading
import time

from .keys import CHAR_KEYS, NAMES

EV_SYN, EV_KEY = 0, 1
KEY_BACKSPACE, KEY_LEFTSHIFT = 14, 42
DEVICE_NAME = b"votyper virtual keyboard"

# ioctl numbers (linux/uinput.h, linux/input.h)
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x5501, 0x5502
EVIOCGNAME = 0x80FF4506  # read device name (up to 255 bytes)

EVENT = struct.Struct("llHHi")  # struct input_event: time(sec, usec), type, code, value
# Typographic characters speech models like to emit -> typeable ASCII.
ASCII_FALLBACK = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                                "–": "-", "—": "-", "…": "..."})


class Keyboard:
    """Types through a virtual keyboard created with /dev/uinput."""

    def __init__(self):
        try:
            self._fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        except PermissionError as e:
            raise RuntimeError("cannot open /dev/uinput: add your user to the "
                               "'input' group (then log in again)") from e
        fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
        for code in {c for c, _ in CHAR_KEYS.values()} | {KEY_BACKSPACE, KEY_LEFTSHIFT}:
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, code)
        # struct uinput_setup: bustype, vendor, product, version, name[80], ff_effects_max
        fcntl.ioctl(self._fd, UI_DEV_SETUP,
                    struct.pack("HHHH80sI", 0x06, 0x1, 0x1, 1, DEVICE_NAME, 0))
        fcntl.ioctl(self._fd, UI_DEV_CREATE)
        time.sleep(0.3)  # let the desktop notice the new device

    def _emit(self, etype: int, code: int, value: int) -> None:
        os.write(self._fd, EVENT.pack(0, 0, etype, code, value))

    def _tap(self, code: int, shift: bool = False) -> None:
        for key, value in ([(KEY_LEFTSHIFT, 1)] * shift + [(code, 1), (code, 0)]
                           + [(KEY_LEFTSHIFT, 0)] * shift):
            self._emit(EV_KEY, key, value)

    def type_text(self, text: str) -> None:
        for ch in text.translate(ASCII_FALLBACK):
            if ch in CHAR_KEYS:         # skip characters we can't type
                self._tap(*CHAR_KEYS[ch])
        self._emit(EV_SYN, 0, 0)

    def backspace(self, count: int) -> None:
        for _ in range(count):
            self._tap(KEY_BACKSPACE)
        self._emit(EV_SYN, 0, 0)

    def close(self) -> None:
        fcntl.ioctl(self._fd, UI_DEV_DESTROY)
        os.close(self._fd)


class KeyListener:
    """Reads every keyboard-like /dev/input device and reports key up/down."""

    def __init__(self):
        self._sel = selectors.DefaultSelector()
        self._stop = threading.Event()
        self._thread = None

    def start(self, feed) -> None:
        for name in sorted(os.listdir("/dev/input")):
            if not name.startswith("event"):
                continue
            try:
                fd = os.open(f"/dev/input/{name}", os.O_RDONLY | os.O_NONBLOCK)
            except PermissionError:
                continue
            dev_name = fcntl.ioctl(fd, EVIOCGNAME, b"\0" * 256).split(b"\0")[0]
            if DEVICE_NAME in dev_name:  # never listen to our own typing (or a passthrough copy)
                os.close(fd)
                continue
            self._sel.register(fd, selectors.EVENT_READ)
        if not self._sel.get_map():
            raise RuntimeError("cannot read /dev/input: add your user to the "
                               "'input' group (then log in again)")
        self._thread = threading.Thread(target=self._loop, args=(feed,), daemon=True)
        self._thread.start()

    def _loop(self, feed) -> None:
        while not self._stop.is_set():
            for key, _ in self._sel.select(timeout=0.5):
                try:
                    data = os.read(key.fd, EVENT.size * 64)
                except OSError:         # device unplugged
                    self._sel.unregister(key.fd)
                    continue
                for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _, _, etype, code, value = EVENT.unpack_from(data, off)
                    if etype == EV_KEY and code in NAMES:
                        feed(NAMES[code], value != 0)

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        for key in list(self._sel.get_map().values()):
            os.close(key.fd)
        self._sel.close()
