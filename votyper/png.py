"""A small PNG reader and writer (8-bit RGB/RGBA, not interlaced), standard library only."""

import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
RGB, RGBA = 2, 6                    # PNG colour types we accept


def read_png(path) -> tuple:
    """Return (width, height, RGBA bytes) for a PNG file."""
    data = Path(path).read_bytes()
    if data[:8] != SIGNATURE:
        raise ValueError("not a PNG file")

    header, compressed, pos = None, bytearray(), 8
    while pos < len(data):                          # the file is a list of chunks
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length                          # length + type + body + checksum
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed += body
        elif kind == b"IEND":
            break

    width, height, depth, colour, _, _, interlaced = header
    if depth != 8 or colour not in (RGB, RGBA) or interlaced:
        raise ValueError("unsupported PNG: need 8-bit RGB or RGBA, not interlaced")
    channels = 4 if colour == RGBA else 3
    rows = _unfilter(zlib.decompress(compressed), width * channels, height, channels)
    return width, height, rows if channels == 4 else _add_alpha(rows)


def write_png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode RGBA pixels as the bytes of a PNG file."""
    stride = width * 4
    rows = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, RGBA, 0, 0, 0)
    return (SIGNATURE + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def _unfilter(raw: bytes, stride: int, height: int, bpp: int) -> bytes:
    """Undo the per-row prediction filters PNG applies before compressing."""
    out, previous = bytearray(), bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = previous[i]
            up_left = previous[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                line[i] = (line[i] + _paeth(left, up, up_left)) & 255
        out += line
        previous = line
    return bytes(out)


def _paeth(left: int, up: int, up_left: int) -> int:
    """Pick whichever neighbour is closest to left + up - up_left."""
    estimate = left + up - up_left
    distances = [(abs(estimate - n), n) for n in (left, up, up_left)]
    return min(distances, key=lambda d: d[0])[1]    # ties keep the order left, up, up-left


def _add_alpha(rgb: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(rgb), 3):
        out += rgb[i:i + 3] + b"\xff"
    return bytes(out)
