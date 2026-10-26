"""The tray icon: the app's sphere, shrunk once per size and dimmed for the blink."""

from functools import lru_cache
from math import ceil
from pathlib import Path

from .png import read_png, write_png

ICON_FILE = Path(__file__).parent / "assets" / "votyper.png"
SIZES = (22, 32, 48, 64)            # the tray picks the one that fits its panel
DIM_OPACITY = 0.25                  # the faded half of the blink


def shrink(width: int, height: int, rgba: bytes, size: int, opacity: float = 1.0) -> bytes:
    """Scale an RGBA picture to size x size by averaging; returns ARGB bytes.

    Colours are averaged weighted by opacity, so edges stay clean instead of
    picking up a dark fringe from transparent pixels.
    """
    step_x, step_y = width / size, height / size
    out = bytearray()
    for dy in range(size):
        y0, y1 = dy * step_y, (dy + 1) * step_y
        for dx in range(size):
            x0, x1 = dx * step_x, (dx + 1) * step_x
            alpha = red = green = blue = area = 0.0
            for sy in range(int(y0), min(height, ceil(y1))):
                row_share = min(sy + 1, y1) - max(sy, y0)
                for sx in range(int(x0), min(width, ceil(x1))):
                    share = row_share * (min(sx + 1, x1) - max(sx, x0))
                    i = (sy * width + sx) * 4
                    weight = share * rgba[i + 3] / 255
                    red, green, blue = (red + weight * rgba[i], green + weight * rgba[i + 1],
                                        blue + weight * rgba[i + 2])
                    alpha += weight
                    area += share
            if alpha:
                red, green, blue = red / alpha, green / alpha, blue / alpha
            out += bytes([round(255 * opacity * alpha / area),
                          round(red), round(green), round(blue)])
    return bytes(out)


@lru_cache(maxsize=None)
def _sphere() -> tuple:
    return read_png(ICON_FILE)


@lru_cache(maxsize=None)
def logo_png(size: int) -> bytes:
    """The logo resized to size x size, as PNG bytes (for the settings window)."""
    width, height, rgba = _sphere()
    argb = shrink(width, height, rgba, size)
    pixels = bytearray(len(argb))           # reorder ARGB -> RGBA for the PNG
    pixels[0::4], pixels[1::4], pixels[2::4], pixels[3::4] = argb[1::4], argb[2::4], argb[3::4], argb[0::4]
    return write_png(size, size, bytes(pixels))


@lru_cache(maxsize=None)
def icons(state: str) -> tuple:
    """Pictures for a state as (size, size, ARGB bytes), drawn once and reused.

    Only the blink's faded phase ("listening_dim") looks different.
    """
    width, height, rgba = _sphere()
    opacity = DIM_OPACITY if state == "listening_dim" else 1.0
    return tuple((s, s, shrink(width, height, rgba, s, opacity)) for s in SIZES)
