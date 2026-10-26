import time
import unittest

from votyper.blinker import Blinker
import tempfile
from pathlib import Path

from votyper.icon import icons, logo_png
from votyper.png import read_png


class BlinkerTest(unittest.TestCase):
    def test_starts_on_then_alternates_and_stops_for_good(self):
        seen = []
        blinker = Blinker(seen.append, period=0.01)
        blinker.start()
        time.sleep(0.15)
        blinker.stop()
        count = len(seen)
        time.sleep(0.05)
        self.assertEqual(seen[:4], [True, False, True, False])
        self.assertGreater(count, 4)
        self.assertEqual(len(seen), count)      # nothing after stop()

    def test_can_be_restarted(self):
        seen = []
        blinker = Blinker(seen.append, period=0.01)
        blinker.start()
        blinker.stop()
        blinker.start()
        blinker.stop()
        self.assertEqual(seen.count(True) >= 2, True)


class IconTest(unittest.TestCase):
    @staticmethod
    def strongest_alpha(state):
        return max(icons(state)[0][2][0::4])        # ARGB: every 4th byte is the alpha

    def test_dim_phase_is_fainter_than_bright(self):
        self.assertGreaterEqual(self.strongest_alpha("listening"), 250)
        self.assertLessEqual(self.strongest_alpha("listening_dim"), 70)

    def test_steady_states_look_the_same(self):
        self.assertEqual(icons("idle"), icons("loading"))

    def test_every_size_has_the_right_amount_of_pixels(self):
        for size, same_size, pixels in icons("idle"):
            self.assertEqual((size, len(pixels)), (same_size, size * size * 4))

    def test_logo_png_is_a_valid_picture_of_the_requested_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "logo.png"
            path.write_bytes(logo_png(28))
            width, height, rgba = read_png(path)
        self.assertEqual((width, height, len(rgba)), (28, 28, 28 * 28 * 4))
        self.assertGreater(max(rgba[3::4]), 200)    # not blank: something is drawn

    def test_pictures_are_drawn_once(self):
        self.assertIs(icons("idle"), icons("idle"))


if __name__ == "__main__":
    unittest.main()
