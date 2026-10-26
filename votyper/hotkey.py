"""Platform-neutral hotkey description, e.g. "F9" or "ctrl+alt+space"."""

from dataclasses import dataclass

MODIFIERS = ("ctrl", "alt", "shift", "meta")
_ALIASES = {"control": "ctrl", "option": "alt", "super": "meta", "win": "meta",
            "cmd": "meta", "command": "meta"}


@dataclass(frozen=True)
class Hotkey:
    key: str                    # lowercase name: "f9", "space", "a", "1"
    modifiers: frozenset = frozenset()

    @classmethod
    def parse(cls, text: str) -> "Hotkey":
        parts = [_ALIASES.get(p.strip().lower(), p.strip().lower())
                 for p in text.split("+") if p.strip()]
        if not parts:
            raise ValueError("empty hotkey")
        *mods, key = parts
        if any(m not in MODIFIERS for m in mods) or key in MODIFIERS:
            raise ValueError(f"bad hotkey {text!r}: use modifiers {MODIFIERS} plus one key")
        return cls(key, frozenset(mods))

    def __str__(self) -> str:
        return "+".join([*(m for m in MODIFIERS if m in self.modifiers), self.key])
