"""Linux key codes (linux/input-event-codes.h) <-> neutral key names."""


def _typing_keys() -> dict:
    """char -> (keycode, needs_shift) for a US layout."""
    rows = [  # (first keycode, unshifted chars, shifted chars)
        (2, "1234567890-=", "!@#$%^&*()_+"),
        (16, "qwertyuiop[]", "QWERTYUIOP{}"),
        (30, "asdfghjkl;'", 'ASDFGHJKL:"'),
        (44, "zxcvbnm,./", "ZXCVBNM<>?"),
    ]
    keys = {" ": (57, False), "\n": (28, False), "\t": (15, False),
            "`": (41, False), "~": (41, True), "\\": (43, False), "|": (43, True)}
    for first, plain, shifted in rows:
        for i, (p, s) in enumerate(zip(plain, shifted)):
            keys[p], keys[s] = (first + i, False), (first + i, True)
    return keys


CHAR_KEYS = _typing_keys()

# keycode -> neutral name (left and right modifiers share one name)
NAMES = {code: ch for ch, (code, shift) in CHAR_KEYS.items() if ch.isalnum() and not shift}
NAMES.update({57: "space", 1: "esc", 15: "tab", 28: "enter", 119: "pause", 70: "scrolllock",
              110: "insert", 111: "delete", 102: "home", 107: "end", 104: "pageup",
              109: "pagedown", 103: "up", 108: "down", 105: "left", 106: "right",
              29: "ctrl", 97: "ctrl", 42: "shift", 54: "shift",
              56: "alt", 100: "alt", 125: "meta", 126: "meta"})
NAMES.update({58 + i: f"f{i}" for i in range(1, 11)})
NAMES.update({87: "f11", 88: "f12"})
NAMES.update({183 + i - 13: f"f{i}" for i in range(13, 25)})
