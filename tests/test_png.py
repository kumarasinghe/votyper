import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from votyper.icon import ICON_FILE
from votyper.png import read_png, write_png


def paeth(left, up, up_left):
    """The PNG spec's predictor, written out independently of the code under test."""
    estimate = left + up - up_left
    pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
    if pa <= pb and pa <= pc:
        return left
    return up if pb <= pc else up_left


def make_png(width, height, pixel_rows, colour=6, filters=None, depth=8):
    """Build a PNG file's bytes, applying a chosen filter to each row."""
    channels = 4 if colour == 6 else 3
    filters = filters or [0] * height
    raw, previous = bytearray(), bytes(width * channels)
    for row, kind in zip(pixel_rows, filters):
        filtered = bytearray([kind])
        for i, value in enumerate(row):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            predicted = [0, left, up, (left + up) // 2, paeth(left, up, up_left)][kind]
            filtered.append((value - predicted) & 255)
        raw += filtered
        previous = row

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


class ReadPngTest(unittest.TestCase):
    def decode(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.png"
            path.write_bytes(data)
            return read_png(path)

    def test_every_filter_type_decodes_to_the_original_pixels(self):
        rows = [bytes((x * 37 + y * 11 + c * 5) % 256 for x in range(5) for c in range(4))
                for y in range(5)]
        for kind in range(5):
            with self.subTest(filter=kind):
                width, height, rgba = self.decode(make_png(5, 5, rows, filters=[kind] * 5))
                self.assertEqual((width, height, rgba), (5, 5, b"".join(rows)))

    def test_different_filters_in_one_image(self):
        rows = [bytes((x * 53 + y * 17) % 256 for x in range(12)) for y in range(5)]
        data = make_png(3, 5, rows, filters=[0, 1, 2, 3, 4])
        self.assertEqual(self.decode(data)[2], b"".join(rows))

    def test_rgb_pictures_get_full_opacity(self):
        rows = [bytes([10, 20, 30, 40, 50, 60])]
        width, height, rgba = self.decode(make_png(2, 1, rows, colour=2))
        self.assertEqual(rgba, bytes([10, 20, 30, 255, 40, 50, 60, 255]))

    def test_rejects_files_that_are_not_png(self):
        with self.assertRaises(ValueError):
            self.decode(b"not a png at all")

    def test_rejects_unsupported_bit_depth(self):
        with self.assertRaises(ValueError):
            self.decode(make_png(1, 1, [bytes(4)], depth=16))

    def test_written_png_reads_back_unchanged(self):
        pixels = bytes((x * 31 + 7) % 256 for x in range(3 * 2 * 4))
        self.assertEqual(self.decode(write_png(3, 2, pixels)), (3, 2, pixels))

    def test_the_app_icon_decodes(self):
        width, height, rgba = read_png(ICON_FILE)       # whatever size the icon currently is
        self.assertGreater(width, 0)
        self.assertEqual(width, height)
        self.assertEqual(len(rgba), width * height * 4)


if __name__ == "__main__":
    unittest.main()
