"""Settings saved between runs (currently just the hotkey)."""

import json
import os


def _path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "votyper", "config.json")


def load() -> dict:
    try:
        with open(_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(**values) -> None:
    config = {**load(), **values}
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w") as f:
        json.dump(config, f, indent=2)
